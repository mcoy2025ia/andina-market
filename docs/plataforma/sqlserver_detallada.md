# SQL Server · guía detallada

> Versión ampliada de [sqlserver.md](sqlserver.md). Mismos identificadores (SQL-01…SQL-09),
> mismo DDL, mismo script de optimización. Lo que añade: cómo lee un optimizador de
> consultas un plan de ejecución, por qué el `CAST` del enunciado original fuerza un
> *scan*, qué hace `IDENTITY_INSERT` por debajo, glosario y preguntas frecuentes.

**Qué vas a lograr aquí:** lo mismo que la versión corta: ejecutar por primera vez el
DDL y el T-SQL del proyecto en un motor SQL Server real, cargar el modelo estrella y
medir la optimización con planes de ejecución. Cierra **E01** y **E02**.

**Tiempo total:** 5 h. **Prerrequisito:** el almacén local construido
(`python scripts/cargar_datos.py --desde-cero`).

---

## Conceptos antes de empezar

### Qué es un plan de ejecución, en términos que no requieren haber visto uno antes

Cuando mandas una consulta SQL, el motor no la ejecuta "como está escrita": un
componente llamado **optimizador** genera varias formas físicas posibles de resolverla
(qué orden de cruces, qué método de acceso a cada tabla, qué algoritmo de *join*) y
elige la que estima más barata según estadísticas sobre el tamaño y la distribución de
los datos. El **plan de ejecución** es esa forma física elegida, representada como un
árbol de operadores. Dos consultas que devuelven el mismo resultado pueden tener planes
radicalmente distintos en costo — eso es exactamente lo que SQL-06/SQL-07 comparan.

### `Index Seek` vs. `Index Scan` vs. `Table Scan`: la diferencia que de verdad importa

- **Table Scan:** el motor lee **todas** las filas de la tabla, una por una, para
  encontrar las que cumplen la condición. Costo proporcional al tamaño total de la
  tabla, sin importar cuántas filas realmente cumplan.
- **Index Scan:** igual que un Table Scan pero recorriendo un índice completo en vez de
  la tabla base — más barato si el índice es más angosto que la tabla, pero sigue
  siendo "leer todo".
- **Index Seek:** el motor usa la estructura del índice (un B-tree, en SQL Server) para
  saltar directamente a las filas que cumplen la condición, sin tocar las que no.
  Costo proporcional al número de filas que **sí** cumplen, no al tamaño de la tabla.

Con 19.270 pedidos, la diferencia entre un *seek* y un *scan* es invisible — el motor
resuelve cualquiera de los dos en milisegundos. Con 500.000 filas (SQL-05), la diferencia
se vuelve medible en segundos y en lecturas lógicas, que es exactamente el punto de
SQL-05 a SQL-07: sin volumen, "optimizar" no tiene nada que demostrar.

### Por qué el `CAST` del enunciado original fuerza un *scan* (el corazón de SQL-06/07)

La causa técnica exacta es lo que en SQL Server se llama **no-SARGable predicate**
(*Search ARGument ABLE*): un predicado es *SARGable* cuando el optimizador puede usarlo
directamente contra un índice para hacer un *seek*. Envolver la columna indexada en una
función (`CAST(columna AS VARCHAR(20))`, `UPPER(columna)`, `columna + 1`, etc.) rompe
esa propiedad: el motor no puede saber, sin evaluar la función para cada fila, si esa
fila cumple la condición — porque el índice está ordenado por el valor **original** de
la columna, no por el resultado de la función aplicada a cada valor. El optimizador
entonces tiene que leer la tabla (o el índice) entero y aplicar el `CAST` fila por fila:
exactamente un *scan*. La consulta reescrita de `02_optimizacion.sql` evita el `CAST` en
ambos lados del cruce, lo que le devuelve al optimizador la posibilidad de un *seek*
directo sobre el índice.

Esto explica por qué en el experimento de referencia (SQLite, documentado en SQL-07)
quitar **solo** el `CAST` —sin tocar nada más— bajó el tiempo de 7,28 s a 0,06 s con
100.000 filas: no fue una reescritura elaborada, fue eliminar la única cosa que le
impedía al motor usar el índice que ya existía.

### Qué hace `SET STATISTICS IO/TIME ON` y por qué importa más que el cronómetro

El tiempo de pared (*wall time*) de una consulta varía por factores externos: si los
datos ya estaban en caché de memoria de una ejecución anterior, carga del sistema, red.
**Lecturas lógicas** (`STATISTICS IO`) cuenta páginas de 8 KB leídas desde el *buffer
pool*, independientemente de si venían de disco o ya estaban en memoria — es una medida
mucho más estable y comparable entre ejecuciones. Por eso SQL-06/SQL-07 pide capturar
ambas, no solo el tiempo: si el tiempo baja pero las lecturas lógicas no, puede ser
casualidad de caché; si las lecturas lógicas bajan de forma proporcional al cambio de
operador (*scan*→*seek*), ahí está la prueba real de que el plan cambió de naturaleza.

### `IDENTITY_INSERT`: por qué el cargador lo necesita

Una columna `IDENTITY` en SQL Server genera su propio valor automáticamente en cada
`INSERT`, y por defecto **rechaza** que el `INSERT` especifique un valor explícito para
ella. El modelo estrella local (`star.py`) ya asigna claves de dimensión estables
(`canal_key`, `categoria_key`, `cliente_key`) que deben preservarse exactamente al
migrar a SQL Server — si SQL Server generara sus propias claves nuevas, cualquier hecho
que referencie la clave original (`fact_pedido.canal_key = 3`) apuntaría a una fila
distinta o inexistente. `SET IDENTITY_INSERT tabla ON` suspende temporalmente esa
generación automática, permitiendo que `cargar_modelo_sqlserver.py` inserte las mismas
claves que ya existen en DuckDB, fila por fila, sin reasignarlas.

### Por qué el tipo de columna monetaria importa tanto como el valor

El proyecto define venta neta como aritmética de **enteros exactos** (pesos colombianos
sin fracciones, ver `config.py` y [README_ETL.md](../../README_ETL.md#calidad-y-publicación)).
`BIGINT` en SQL Server representa enteros exactos hasta ~9,2×10¹⁸ sin ningún error de
redondeo. `DECIMAL(p,s)` también es exacto, pero introduce una escala (decimales) que
el proyecto no usa y que, si el DDL la declarara por error, permitiría guardar valores
fraccionarios que el resto del pipeline nunca produce — una inconsistencia silenciosa.
`FLOAT`/`REAL` son los peligrosos de verdad: son de punto flotante binario, y sumar
muchos valores monetarios en coma flotante puede acumular error de redondeo que, a la
escala de miles de millones de pesos del total del caso, deja de ser despreciable. Por
eso SQL-03 pide verificar los tipos explícitamente con una consulta a `sys.columns`, no
confiar en que "el número salió bien" en una sola prueba.

---

## SQL-01 · Levantar SQL Server ⏱️ 20 min

(Mismo comando Docker, misma base `andina`.)

**🧠 Por qué Docker y no Fabric Warehouse ni Azure SQL para este bloque:** el objetivo
de SQL-02 a SQL-07 es medir comportamiento de **SQL Server real** — el motor que el
enunciado pide, con su optimizador de costos y sus tipos de índice. Fabric Warehouse usa
un motor T-SQL compatible pero con un optimizador y un modelo de almacenamiento
distintos (columnar distribuido sobre OneLake), por lo que un plan de ejecución ahí no
es comparable al de SQL Server on-premises/Docker. Azure SQL Database sí es SQL Server
real, pero cobra por hora activa — válido como alternativa, pero Docker es gratis y
suficiente para el volumen de este experimento.

**❌ Catálogo extendido de errores**

| Error | Causa | Qué hacer |
|---|---|---|
| *«port is already allocated»* | Otro proceso (u otro contenedor) ya usa el puerto 1433 | `-p 1434:1433` y conéctate a `localhost,1434` |
| El contenedor se reinicia en bucle | La contraseña no cumple la política de complejidad de SQL Server (mínimo 8 caracteres, 3 de 4 categorías: mayúsculas, minúsculas, números, símbolos) | Usa una contraseña que cumpla explícitamente las cuatro categorías |
| `docker logs` muestra `Error: ... /var/opt/mssql` o problemas de permisos | En algunos sistemas con SELinux/permisos de volumen estrictos, el contenedor no puede escribir su almacenamiento interno | Añade `-v sqlserver_data:/var/opt/mssql` para usar un volumen Docker administrado en vez de confiar en el almacenamiento efímero del contenedor |
| Te conectas pero `SELECT @@VERSION` no responde o tarda mucho | El contenedor sigue inicializando internamente aunque `docker ps` ya lo muestre `Up` | Espera 30-60 s más tras el primer `docker ps` y reintenta |

**⚠️ No pongas esa contraseña en ningún archivo del repositorio.**

**📎 Evidencia:** `evidencia/sqlserver/01_docker.txt`.

---

## SQL-02 · Ejecutar el DDL ⏱️ 30 min ⭐

(Mismos pasos: ejecutar `sqlserver/ddl_tsql.sql` completo, anotar errores sin corregirlos
en silencio, verificar esquemas/tablas/vistas/índices creados.)

**🧠 Por qué "anotar el error y seguir" en vez de corregir sobre la marcha:** el DDL
nunca se ejecutó contra un motor real (ver
[docs/ESTADO_IMPLEMENTACION.md](../ESTADO_IMPLEMENTACION.md)), así que cualquier
discrepancia entre lo que DuckDB acepta y lo que T-SQL exige es información real sobre
el estado del proyecto, no un defecto a esconder. Corregir en caliente, sin registrar
qué falló, destruye exactamente el dato que esta tarea existe para producir: la lista de
diferencias reales entre dialectos.

**🧠 Qué tipo de errores son los más probables, por experiencia con DuckDB → T-SQL:**
diferencias de sintaxis en tipos (`TEXT` vs `NVARCHAR(MAX)`), restricciones `CHECK` con
funciones no soportadas igual, el orden de creación si hay referencias circulares entre
FKs, y nombres reservados de palabra clave que DuckDB permite como identificador y
T-SQL no sin corchetes (`[...]`).

**📎 Evidencia:** `evidencia/sqlserver/02_ddl.txt` con la salida del script **y la lista
de errores si los hubo**.

**Cierra:** la mitad de **E01**.

---

## SQL-03 · Cargar el modelo estrella ⏱️ 40 min

(Mismos pasos: `pyodbc`, driver ODBC 18, variable `DWH_CONNECTION_STRING`, primero plan,
luego `--aplicar --entorno-pruebas`.)

**🧠 Por qué el modo "plan" existe antes del modo que escribe:** es la misma filosofía
de seguridad que ya aplica `despachar_reporte.py` (que no envía correo sin autorización
explícita) y `importar_etiquetas.py` (que se niega a importar sin revisión humana): un
script que puede escribir en un entorno externo real debería, por defecto, **no**
escribir, y requerir una confirmación explícita (`--aplicar --entorno-pruebas`) para
hacerlo. El modo plan te deja ver exactamente cuántas filas se moverían antes de
comprometerte a la carga real.

**🧠 Qué verifica realmente la consulta de tipos del paso 6:** no solo que la columna
"se ve numérica" — verifica `precision` y `scale` exactos. Un `BIGINT` correcto no tiene
`scale` (no aplica); si la consulta devolviera `decimal` con `scale > 0`, sabrías que
hay fracciones representables donde el proyecto nunca las produce, lo cual sería una
discrepancia de esquema real aunque los valores actuales sean todos enteros.

**❌ Catálogo extendido de errores**

| Error | Causa | Qué hacer |
|---|---|---|
| `[08001] ... SSL Provider: The certificate chain was issued by an authority that is not trusted` | El driver exige validar el certificado TLS y el de Docker es autofirmado | Confirma que `TrustServerCertificate=yes` está en la cadena de conexión (ya está en el ejemplo) |
| `IDENTITY_INSERT is already ON for table ...` | Una ejecución anterior falló a mitad de camino y dejó `IDENTITY_INSERT` activo en otra tabla | SQL Server solo permite una tabla con `IDENTITY_INSERT ON` por sesión; revisa que el script lo desactive en la tabla anterior antes de activarlo en la siguiente, o cierra y abre una conexión nueva |
| Los conteos no cuadran pero no hay error | Una carga parcial previa dejó filas a medias | Trunca las tablas `gold.*` en SQL Server y repite la carga desde cero |

**📎 Evidencia:** `evidencia/sqlserver/03_carga.txt` con los conteos, la suma y los tipos.

**Cierra:** **E01**.

---

## SQL-04 · Ejecutar venta y recompra ⏱️ 40 min

(Mismos pasos: ejecutar `sqlserver/01_ventas_recompra.sql`, comparar fila a fila contra
el equivalente DuckDB.)

**🧠 Por qué "fila a fila" y no solo el total:** el total puede coincidir por
casualidad incluso si la distribución mensual está mal (dos meses que se compensan entre
sí). Comparar cada fila de la serie mensual, incluyendo los meses sin ventas que deben
aparecer en cero, es lo único que confirma que el `JOIN`/`GROUP BY` con el calendario
completo (la "tabla de meses" que resuelve A04, meses vacíos) funciona igual en ambos
dialectos — no solo que las sumas globales coinciden.

**🧠 Qué revisar primero si una fila no coincide:** el dialecto de fecha. `DATEADD`,
`DATEDIFF` y el formato de literales de fecha (`'2026-01-01'`) tienen semántica distinta
entre DuckDB y T-SQL en casos de borde (fin de mes, años bisiestos); es el punto más
probable de divergencia real entre los cuatro dialectos SQL del proyecto.

**📎 Evidencia:** `evidencia/sqlserver/04_tsql.txt`, `04_duckdb.txt` y `04_diferencias.txt`.

**Cierra:** la mitad de **E02**.

---

## SQL-05 · Generar volumen para la prueba de optimización ⏱️ 30 min

(Mismo bucle `WHILE` para llegar a ~500.000 filas en `dbo.pedidos_big` y
`dbo.tickets_big`.)

**🧠 Por qué ~500.000 y no, por ejemplo, 50.000 o 5 millones:** es el mismo orden de
magnitud usado en el experimento de referencia con SQLite (documentado en SQL-07), lo
que permite comparar la *forma* del problema (cuánto se agrava el *scan* al crecer el
volumen) aunque los tiempos absolutos no sean comparables entre motores distintos. Un
volumen demasiado pequeño no deja que el costo del *scan* se separe visiblemente del
*seek*; uno demasiado grande hace que la prueba tome minutos en vez de segundos sin
añadir nada conceptual.

**📎 Evidencia:** `evidencia/sqlserver/05_volumen.txt`.

---

## SQL-06 · Medir la consulta original ⏱️ 30 min ⭐

(Mismos pasos: `SET STATISTICS IO/TIME ON`, plan de ejecución real, medir sin índices y
luego con los índices propuestos.)

**🧠 Por qué medir primero sin índices y luego con índices, en vez de solo con
índices:** para aislar dos efectos distintos que de otro modo se confunden: (1) el
efecto de tener o no un índice adecuado, y (2) el efecto del `CAST` que impide usarlo
aunque el índice exista. Si solo midieras "con índices" sobre la consulta original,
seguirías viendo un *scan* por el `CAST` y podrías concluir erróneamente que "los
índices no ayudan", cuando el problema real es el predicado no-SARGable.

**🧠 Qué son `INCLUDE` columns en un índice, y por qué el índice propuesto las usa:**
una columna en `INCLUDE` se almacena en las hojas del índice sin formar parte de la
clave de ordenamiento. Esto permite un **índice de cobertura** (*covering index*): si
todas las columnas que la consulta necesita (clave de búsqueda + las de `INCLUDE`) están
en el índice, el motor puede resolver la consulta entera leyendo solo el índice, sin
volver a la tabla base para buscar las demás columnas (lo que se llama evitar un *key
lookup*).

**📎 Evidencia:** `evidencia/sqlserver/06_original_plan.png`, `06_original_stats.txt`.

---

## SQL-07 · Medir la consulta reescrita ⏱️ 30 min ⭐

(Mismos pasos: ejecutar `02_optimizacion.sql`, verificar resultados idénticos con
`EXCEPT`, llenar la tabla comparativa.)

**🧠 Por qué `EXCEPT` y no solo comparar el `COUNT(*)` de ambos resultados:** dos
conjuntos de filas pueden tener el mismo número de filas sin ser el mismo conjunto
(podrían diferir en cuáles filas incluyen, no solo en cuántas). `EXCEPT` devuelve
exactamente las filas que están en un lado y no en el otro — si el resultado de la resta
es `0` en ambas direcciones, los conjuntos son idénticos fila por fila, no solo del
mismo tamaño.

**🧠 Qué hace la reescritura de fondo, más allá de "quitar el CAST":** típicamente,
reescribir para evitar un predicado no-SARGable implica comparar columnas del mismo tipo
en ambos lados del cruce (en vez de forzar una conversión de tipo en una de ellas) y/o
reestructurar la condición para que la columna indexada quede "limpia" en un lado de la
comparación. El resultado es que el optimizador puede evaluar el predicado directamente
contra la estructura del índice sin evaluar ninguna función fila por fila.

**📎 Evidencia:** `evidencia/sqlserver/07_reescrita_plan.png`, `07_reescrita_stats.txt`,
`07_comparacion.md`.

**Cierra:** **E02**.

---

## SQL-08 · Usuario de solo lectura y reporte ODBC ⏱️ 30 min

(Mismos pasos: `CREATE LOGIN`/`CREATE USER`/`GRANT SELECT` solo sobre `gold`, probar
`reporte_ventas.py` con ese usuario.)

**🧠 Qué garantiza realmente `GRANT SELECT ON SCHEMA::gold` (y por qué no alcanza con
"confiar en que el script solo lee"):** el permiso se aplica a **nivel del motor**, no
del script — así que ni un error de programación ni un uso malicioso de las credenciales
puede escribir o leer fuera de `gold`, sin importar qué haga el código Python que las
use. Esto es justo lo contrario del patrón que corregía el PR original (usuario `admin`
con contraseña en el código): con `admin`, cualquier *bug* o *exploit* del script tiene
acceso total a la base; con `reporte_ro`, el daño máximo posible está acotado por el
`GRANT` mismo, independientemente del código.

**📎 Evidencia:** `evidencia/sqlserver/08_reporte.txt` **con la contraseña tapada**.

---

## SQL-09 · Limpiar ⏱️ 10 min

(Mismos pasos: `DROP TABLE` de las tablas grandes, `docker stop`.)

**📎 Evidencia:** `evidencia/sqlserver/09_limpieza.txt`.

---

## Glosario

| Término | Qué significa aquí |
|---|---|
| **Plan de ejecución** | La forma física elegida por el optimizador para resolver una consulta; representable como árbol de operadores |
| **Index Seek / Scan / Table Scan** | Tres formas de acceso a datos, de costo proporcional a lo que se busca (seek) o al tamaño total leído (scan) |
| **Predicado SARGable** | Una condición que el optimizador puede usar directamente contra un índice sin evaluar una función fila por fila |
| **Lecturas lógicas** | Páginas de 8 KB leídas desde el buffer pool; medida estable de costo, menos sensible a caché que el tiempo de pared |
| **Índice de cobertura (covering index)** | Un índice que incluye todas las columnas que una consulta necesita, evitando volver a la tabla base |
| **`IDENTITY_INSERT`** | Interruptor de sesión que permite insertar valores explícitos en una columna `IDENTITY`, preservando claves ya asignadas |
| **`EXCEPT`** | Operador de conjuntos que devuelve filas presentes en un resultado y ausentes en otro; útil para probar igualdad exacta entre dos resultados |

## Preguntas frecuentes de este bloque

**Si el DDL falla en varios puntos, ¿es un fracaso de la tarea?**
No — es el resultado esperado de ejecutar por primera vez un DDL escrito sin motor
donde probarlo (ver la nota al inicio de [sqlserver.md](sqlserver.md)). La lista de
errores exactos **es** el entregable de SQL-02, no un efecto secundario indeseado.

**¿Por qué comparar contra SQLite en SQL-07 si el enunciado pide SQL Server?**
El experimento en SQLite (`sqlserver/optimizacion/`) se hizo antes de tener un SQL
Server real disponible, y se documenta explícitamente como "forma del problema, no
tiempos comparables" (ver la nota en la versión corta). SQL-06/SQL-07 son los pasos que
convierten esa evidencia preliminar en una medición real en el motor que pide la prueba.

**¿Por qué no usar directamente Azure SQL Database o Fabric Warehouse para ahorrarse
Docker?**
Fabric Warehouse no es SQL Server (ver el recuadro de conceptos arriba): sus planes de
ejecución no son comparables a los de SQL Server para esta prueba específica. Azure SQL
Database sí lo es y es una alternativa válida, pero cobra por hora activa; Docker local
es gratis y suficiente para el volumen de esta prueba.

## Para profundizar (documentación oficial)

- Planes de ejecución en SQL Server: <https://learn.microsoft.com/sql/relational-databases/performance/execution-plans>
- Predicados SARGable y optimización de índices: <https://learn.microsoft.com/sql/relational-databases/indexes/>
- `SET STATISTICS IO`/`TIME`: <https://learn.microsoft.com/sql/t-sql/statements/set-statistics-io-transact-sql>
- `IDENTITY_INSERT`: <https://learn.microsoft.com/sql/t-sql/statements/set-identity-insert-transact-sql>
