# Microsoft Fabric · guía detallada

> Versión ampliada de [fabric.md](fabric.md). Mismos identificadores (FAB-01…FAB-11),
> mismos comandos y mismas carpetas de evidencia. Lo que añade: por qué la capacidad de
> Fabric se factura distinto a Databricks, qué es realmente OneLake, por qué la prueba
> de transacción (FAB-08) es la más valiosa de todo el roadmap, un glosario y preguntas
> frecuentes.

**Qué vas a lograr aquí:** lo mismo que la versión corta: ejecutar el ETL en un
Lakehouse de Fabric, correr los doce escenarios, verificar si Warehouse soporta
transacción multi-tabla, y dejar listo el modelo semántico para Power BI. Cierra **E04**
en Fabric y prepara **E03**.

**Tiempo total:** 6 h. **Prerrequisito:** una capacidad Fabric asignada.

---

## Conceptos antes de empezar

### Qué es Fabric, en una frase que no es marketing

Fabric es una plataforma SaaS (no te da máquinas virtuales que administres) donde varios
motores distintos —Spark (notebooks/Lakehouse), un motor de *data warehouse* en T-SQL
(Warehouse), un motor de series de tiempo (KQL), Power BI— comparten **un mismo
almacenamiento físico** llamado OneLake, y **una misma capacidad de cómputo** que tú
contratas como un solo recurso (el SKU, p. ej. F2, F8, F64). Esa es la diferencia
estructural con Databricks: ahí el cómputo (clústeres, SQL warehouses, serverless) se
contrata y factura por producto; en Fabric todo sale de la misma "bolsa" de **Capacity
Units** (CU) de la capacidad que asignaste.

### Por qué todo "cuelga de una capacidad"

Una capacidad Fabric es, conceptualmente, una cuota de CU-segundos disponibles. Cada
operación —leer una tabla en un notebook, refrescar un modelo semántico, correr una
consulta en Warehouse— consume CU de esa cuota mientras corre. Si la cuota se agota (hay
un mecanismo de "sobregiro" con *smoothing* y *throttling* antes de bloquear), las
operaciones se ralentizan o se ponen en cola. Por eso **pausar la capacidad al terminar
cada sesión (FAB-11)** es la palanca de costo más grande: una capacidad encendida cobra
por el tiempo que está activa, la estés usando o no — muy distinto de serverless en
Databricks, que factura por uso real (ver
[databricks_detallada.md](databricks_detallada.md)).

### OneLake: por qué Direct Lake no "importa" nada

OneLake es un único *data lake* lógico por organización, en formato Delta, compartido
por todos los workspaces de Fabric (es, con matices, "un ADLS Gen2 que viene con la
suscripción"). Cuando un Lakehouse guarda tablas, en realidad está escribiendo archivos
Delta en OneLake. Un modelo semántico en modo **Direct Lake** no copia esos datos a la
memoria del motor analítico (como sí hace el modo *Import* de Power BI): lee los
*archivos Parquet subyacentes directamente*, usando las estadísticas del log de Delta
para decidir qué *row groups* cargar en memoria bajo demanda. El resultado práctico es
que un refresco de datos en el Lakehouse puede estar disponible para Power BI casi sin
retraso y sin "duplicar" el dato en otro almacenamiento — pero a cambio, las medidas DAX
complejas pueden tener un comportamiento de rendimiento distinto al de un modelo
importado, porque parte del trabajo de filtrado ocurre contra archivos Parquet en vez de
contra estructuras ya optimizadas para DAX en memoria.

### Lakehouse vs. Warehouse: por qué el proyecto usa los dos

Un **Lakehouse** en Fabric expone las mismas tablas de dos formas: como tablas Delta
accesibles desde Spark (`Tables`, lo que usa el notebook), y automáticamente como un
**punto de conexión SQL de solo lectura** (*SQL analytics endpoint*) que traduce T-SQL
sobre esas mismas tablas Delta. Un **Warehouse** es un motor distinto: un *data
warehouse* transaccional en T-SQL con **escritura** nativa, DDL completo y, lo que hace
a FAB-08 interesante, **soporte real de `BEGIN TRANSACTION`/`COMMIT`/`ROLLBACK` sobre
varias tablas a la vez**. El Lakehouse no ofrece eso: su "escritura" pasa por Spark, que
hereda las limitaciones de Delta descritas en
[databricks_detallada.md](databricks_detallada.md#por-qué-delta-no-tiene-transacción-entre-tablas-y-qué-hace-el-proyecto-en-su-lugar).
Por eso el proyecto ejecuta el ETL en el Lakehouse (porque el notebook es PySpark) pero
usa un Warehouse aparte solo para la pregunta de FAB-08.

### Capacity Units: de dónde sale el "SKU"

Los SKU de Fabric (F2, F4, F8, …, F64, …) son múltiplos de una unidad base de CU/segundo.
Duplicar el SKU duplica la cuota de CU disponible por segundo, lo que generalmente
permite más concurrencia y cargas más grandes, no necesariamente "el doble de rápido"
una sola consulta aislada. Un Trial de Fabric usa una capacidad de evaluación con cuota
limitada en el tiempo, sin costo pero también sin el botón de pausa con el mismo efecto
económico (porque no se factura por hora).

---

## FAB-01 · Confirmar capacidad y crear el workspace ⏱️ 15 min

(Mismos pasos que la versión corta.)

**🧠 Por qué importa el SKU exacto y no solo "si hay capacidad o no":** el costo por
hora de una F64 es considerablemente mayor que el de una F8, y ambos escalan de forma
distinta frente al volumen del proyecto (19.270 pedidos es pequeño para cualquier SKU).
Anotar el SKU real evita que la lámina de FinOps use una cifra genérica de internet en
vez del contrato real que tienes.

**❌ Catálogo extendido de errores**

| Error | Causa | Qué hacer |
|---|---|---|
| El workspace nuevo no muestra la opción de asignar capacidad | Estás en un workspace de tipo "Mi área" (personal), que no admite asignación de capacidad Fabric | Crea un workspace de tipo "Workspace" normal desde cero |
| La capacidad aparece pero en estado "Paused" y no deja crear el Lakehouse | Quedó pausada de una sesión anterior | Reanúdala desde **Configuración → Capacidades** antes de seguir |
| No ves ninguna capacidad en la lista, ni siquiera un Trial | La organización no tiene Fabric habilitado o el Trial expiró | Esto es un bloqueador real: se necesita que un administrador del tenant habilite Fabric o renueve/active un Trial |

**📎 Evidencia:** `evidencia/fabric/01_capacidad.png`.

---

## FAB-02 · Crear el Lakehouse ⏱️ 10 min

(Sin cambios.)

**🧠 Qué pasa por debajo:** crear un Lakehouse reserva, dentro de OneLake, un espacio
lógico con dos vistas del mismo almacenamiento: `Tables` (formato Delta, gestionado,
accesible por SQL y Spark) y `Files` (archivos sin estructura obligatoria, lo que usa
este proyecto para los CSV crudos antes de que el notebook los procese).

**📎 Evidencia:** `evidencia/fabric/02_lakehouse.png`.

---

## FAB-03 · Subir los CSV ⏱️ 15 min

(Sin cambios. Ruta exacta `Files/andina/raw/`.)

**🧠 Por qué la ruta exacta importa tanto aquí:** a diferencia de Databricks (donde el
nombre de tres partes en Unity Catalog desacopla el nombre lógico de la ubicación
física), en el modo Fabric del notebook la ruta `Files/andina/raw` **es** literalmente
la ruta que Spark usa para leer, sin una capa de catálogo entre medio. Un acento,
mayúscula o carpeta distinta rompe la lectura sin ambigüedad.

**📎 Evidencia:** `evidencia/fabric/03_archivos.png`.

---

## FAB-04 · Importar el notebook y adjuntar el Lakehouse ⏱️ 15 min

(Sin cambios. El paso que más se olvida —adjuntar el Lakehouse como predeterminado— sigue igual.)

**🧠 Por qué "adjuntar como predeterminado" es necesario y no solo cosmético:** en
Fabric, una ruta relativa como `Files/andina/raw` dentro de un notebook se resuelve
contra el Lakehouse marcado como predeterminado para esa sesión del notebook. Sin un
Lakehouse predeterminado, esa ruta relativa no tiene contra qué resolverse y Spark la
trata como inexistente — de ahí el error `Path does not exist`.

**📎 Evidencia:** `evidencia/fabric/04_notebook.png`.

---

## FAB-05 · Primera ejecución completa ⏱️ 45 min ⭐

(Mismos pasos, misma tabla de cifras esperadas que la versión corta.)

**🧠 Por qué la primera corrida es más lenta aquí que en Databricks serverless:**
Fabric arranca un *pool* de Spark dedicado a la sesión del notebook (aunque sea un pool
"a demanda"), lo que incluye un tiempo de arranque de instancias que serverless de
Databricks, pensado para sesiones muy cortas, suele minimizar de otra forma. No es un
error ni una señal de mala configuración: es parte del modelo de arranque de Fabric.

**❌ Catálogo extendido de errores** (añade a la tabla corta)

| Error | Causa | Qué hacer |
|---|---|---|
| La celda 5 falla con un error de permisos sobre `Tables` | La capacidad está pausada o se pausó a mitad de la sesión | Reanuda la capacidad y vuelve a intentar desde la celda que falló |
| Las cifras de la celda 8 difieren solo en los "insertados" de clientes | Subiste una versión distinta de `clientes.csv` a la de `data/original/` | Verifica el hash del archivo subido contra el original con `python -c "import hashlib;print(hashlib.sha256(open('data/original/clientes.csv','rb').read()).hexdigest())"` |

**📎 Evidencia:** exporta el notebook ejecutado →
`evidencia/fabric/05_primera_corrida.ipynb` + captura de la celda 13.

**Cierra:** **E04-01** en Fabric.

---

## FAB-06 · Comprobar las tablas en el Lakehouse ⏱️ 10 min

(Mismo SQL y mismas cifras que la versión corta.)

**🧠 Qué es el *SQL analytics endpoint* exactamente:** no es un motor T-SQL separado con
su propia copia de los datos — es una capa de traducción que expone las mismas tablas
Delta del Lakehouse como si fueran tablas SQL Server, de solo lectura, sin necesidad de
mover ni duplicar nada. Por eso las cifras tienen que coincidir exactamente con las que
viste en la celda 13 del notebook: es la misma tabla física vista desde otra puerta.

**📎 Evidencia:** `evidencia/fabric/06_tablas.png` + `06_consultas.txt`.

---

## FAB-07 · Los doce escenarios ⏱️ 2–3 h

(Son los mismos doce escenarios documentados en
[databricks_detallada.md#dbx-08--los-doce-escenarios](databricks_detallada.md#dbx-08--los-doce-escenarios),
con las diferencias de sintaxis ya señaladas en la versión corta: rutas `Files/...` en
vez de `/Volumes/...`, nombres de tabla de una parte, subida de archivos por UI.)

**🧠 Lo único que cambia de fondo respecto a Databricks:** nada del *mecanismo*. Delta es
Delta en ambas plataformas — el log de transacciones, el *time travel*, la ausencia de
transacción multi-tabla son propiedades del **formato**, no de quién lo opera. Por eso
repetir los doce escenarios en Fabric no es "redundante": es la comprobación de que el
diseño de publicación (`run_id` + puntero) no depende de un detalle específico de
Databricks, sino de cómo funciona Delta en general.

**📎 Evidencia:** `evidencia/fabric/07_e04-*`.

---

## FAB-08 · La prueba que solo Fabric permite ⏱️ 45 min ⭐⭐

(Mismos pasos y mismo SQL que la versión corta: crear `dbo.t_a`/`dbo.t_b` en un
Warehouse, probar `ROLLBACK` y luego `COMMIT`.)

**🧠 Por qué esto es posible en Warehouse y no en el Lakehouse:** un Warehouse de Fabric
es un motor T-SQL con un **log de transacciones propio** que cubre todas las tablas del
Warehouse a la vez — la misma idea que usa SQL Server o DuckDB (ver
[README_ETL.md](../../README_ETL.md#modelo-y-transacción): *"la transacción DuckDB
confirma Silver, cuarentena, incidencias, watermark, Gold, estrella y
`publicacion_actual` juntos"*). El Lakehouse, en cambio, no tiene ese log compartido:
cada tabla Delta tiene el suyo, independiente. Por eso la hipótesis de FAB-08 no es "¿es
posible una transacción en Fabric?" sino más precisamente **"¿en cuál de los dos motores
de Fabric, y con qué consecuencias de arquitectura si se usara ese motor en vez del
patrón `run_id`?"**.

**🧠 Qué significa exactamente "hipótesis confirmada" aquí:** si el `ROLLBACK` deja
ambas tablas en 0 filas, significa que Warehouse sí ofrece atomicidad real entre tablas.
Eso **no** significa automáticamente que el proyecto deba migrar su Gold de Delta a
Warehouse — significa que, **si** se decidiera usar Warehouse como destino de
publicación, el patrón `run_id` + puntero deja de ser necesario y se podría volver a un
diseño con `BEGIN TRANSACTION` real, más simple de razonar. Es una pieza de evidencia
para una decisión de arquitectura futura, no un cambio que se aplique solo.

**🧠 Por qué la prueba del `COMMIT` (paso 4) no es opcional:** sin ella, un `ROLLBACK`
que deja las tablas en 0 filas podría significar simplemente que el `INSERT` nunca llegó
a ejecutarse (por ejemplo, por un error de sintaxis silencioso). El `COMMIT` descarta esa
alternativa: si tras el `COMMIT` ambas tablas sí tienen su fila, entonces el `ROLLBACK`
anterior **deshizo** un cambio que sí había ocurrido — eso es lo que prueba atomicidad,
no la ausencia de escritura.

**❌ Qué hacer si la prueba da un resultado mixto** (por ejemplo, una tabla con la fila y
la otra sin ella tras el `ROLLBACK`): eso sería un hallazgo real y significativo —
indicaría que la "transacción" no es realmente atómica entre tablas en esa configuración
de Warehouse. Documéntalo exactamente así, con las dos consultas de verificación; no lo
reintentes esperando otro resultado.

**📎 Evidencia:** `evidencia/fabric/08_transaccion.txt` con los cuatro resultados y
`08_ddl_warehouse.txt` con la lista de lo que no soportó del DDL original.

---

## FAB-09 · Modelo semántico Direct Lake ⏱️ 30 min

(Mismos pasos y misma tabla de relaciones que la versión corta.)

**🧠 Por qué las dimensiones no se relacionan entre sí (y por qué Power BI a veces
propone esa relación de todos modos):** en un esquema en estrella, cada dimensión se
relaciona únicamente con la(s) tabla(s) de hechos; dos dimensiones nunca se relacionan
directamente entre sí, porque cualquier análisis que las cruce debe pasar por el hecho
(p. ej. "canal vs. fecha" solo tiene sentido a través de los pedidos que ocurrieron en
ese canal y esa fecha). El detector automático de relaciones de Power BI a veces
sugiere una relación directa entre dos dimensiones si comparten una columna con nombre o
tipo parecido — hay que rechazarla explícitamente, porque introduciría una ruta de
filtrado ambigua o directamente incorrecta.

**📎 Evidencia:** `evidencia/fabric/09_modelo.png`.

**Sigue en:** [powerbi_detallada.md](powerbi_detallada.md), que usa este modelo.

---

## FAB-10 · Programar el notebook ⏱️ 20 min *(opcional)*

(Sin cambios: diario, 5:00 a. m., zona Bogotá, deshabilitado hasta decidir operarlo.)

**📎 Evidencia:** `evidencia/fabric/10_schedule.png`.

---

## FAB-11 · Pausar la capacidad ⏱️ 5 min 💰

(Sin cambios.)

**🧠 Por qué "pausar" y no "borrar la capacidad":** pausar detiene la facturación por
cómputo sin perder la configuración de la capacidad (SKU, región, workspaces asignados):
reanudarla la deja lista de inmediato. Borrarla significa volver a aprovisionar desde
cero y, dependiendo de la configuración de tu organización, podría requerir de nuevo
permisos de administrador.

**📎 Evidencia:** `evidencia/fabric/11_pausa.png`.

---

## Glosario

| Término | Qué significa aquí |
|---|---|
| **Capacidad (capacity)** | El recurso de cómputo que compras en Fabric, medido en SKU (F2…F64); de ahí salen las CU que consume cualquier operación en cualquier workspace asignado a ella |
| **CU (Capacity Unit)** | La unidad de cómputo normalizada de Fabric; análoga en propósito al DBU de Databricks, pero facturada por capacidad activa, no por consulta individual |
| **OneLake** | El almacenamiento Delta único compartido por todos los motores y workspaces de Fabric de una organización |
| **Lakehouse** | Tablas Delta + archivos, accesibles por Spark y por un punto de conexión SQL de solo lectura automático |
| **Warehouse** | Motor T-SQL con escritura nativa y transacciones multi-tabla reales, distinto del Lakehouse |
| **Direct Lake** | Modo de un modelo semántico que lee los archivos Delta subyacentes directamente, sin copiar los datos a otro almacenamiento (a diferencia de *Import*) |
| **SQL analytics endpoint** | La vista T-SQL de solo lectura que Fabric genera automáticamente sobre las tablas de un Lakehouse |

## Preguntas frecuentes de este bloque

**¿Por qué validar Fabric si ya se validó Databricks (o al revés)?**
Porque el diseño del proyecto se declara portable entre ambos (ver
[docs/08_traslado_delta.md](../08_traslado_delta.md)), y esa afirmación solo se sostiene
si de verdad corre en los dos, no solo en uno. La evidencia de cada plataforma se guarda
por separado precisamente para no mezclar "funciona en A" con "funciona en A y B".

**Si FAB-08 confirma que Warehouse soporta transacciones multi-tabla, ¿hay que migrar
Gold de Delta a Warehouse?**
No necesariamente, y el proyecto no lo decide por su cuenta: es un dato para una
decisión de arquitectura que depende de otros factores (costo, si el resto del pipeline
sigue siendo Spark, compatibilidad del DDL — ver el propio FAB-08, paso 5). Lo que sí
cambia es que la pregunta "¿por qué no usar una transacción real?" pasa de ser una
limitación asumida de la plataforma a una decisión de diseño explícita y justificada.

**¿Por qué el notebook en modo Fabric no usa nombres de tres partes como en
Databricks?**
Porque un Lakehouse de Fabric no tiene el mismo concepto de catálogo/esquema de tres
niveles que Unity Catalog: el "catálogo" implícito es el Lakehouse mismo (ver
`T()` en la celda 2, descrito en
[databricks_detallada.md](databricks_detallada.md#dbx-05--importar-el-notebook-️-10-min)).

## Para profundizar (documentación oficial)

- Conceptos de capacidad y CU en Fabric: <https://learn.microsoft.com/fabric/>
- OneLake: <https://learn.microsoft.com/fabric/onelake/>
- Direct Lake: <https://learn.microsoft.com/fabric/get-started/direct-lake-overview>
- Warehouse vs. Lakehouse: <https://learn.microsoft.com/fabric/data-warehouse/>
