# Power BI y DAX · guía detallada

> Versión ampliada de [powerbi.md](powerbi.md). Mismos identificadores (PBI-01…PBI-09),
> mismas medidas DAX, mismos valores de referencia. Lo que añade: cómo evalúa DAX cada
> medida por debajo (contexto de fila vs. contexto de filtro), por qué `tiene_datos` es
> obligatorio y no cosmético, más pruebas de borde, glosario y preguntas frecuentes.

**Qué vas a lograr aquí:** lo mismo que la versión corta: instalar las cinco medidas DAX
en un motor real y verificarlas contra siete valores calculados en SQL. Cierra **E03**.

**Tiempo total:** 3 h. **Prioridad: la más alta de todo el roadmap.**

---

## Conceptos antes de empezar

### Qué hace distinto a DAX de SQL (y por qué esto importa para leer las cinco medidas)

En SQL, una consulta define explícitamente de qué filas parte (`FROM`/`WHERE`) y cómo
las agrupa. En DAX, una medida no tiene un `FROM`: se evalúa dentro de un **contexto**
que le llega desde fuera —una celda de una matriz, un filtro de segmentación, otra
medida que la invoca— y ese contexto determina qué filas "existen" en el momento de
calcular. Hay dos tipos de contexto:

- **Contexto de fila:** existe dentro de funciones como `SUMX`, fila por fila de una
  tabla. `SUMX(gold_fact_pedido, gold_fact_pedido[valor_bruto] - gold_fact_pedido[descuento])`
  recorre cada pedido y calcula `valor_bruto - descuento` fila por fila, antes de sumar.
- **Contexto de filtro:** el conjunto de filas visibles dado todo lo que filtra la
  visual (filas/columnas de una matriz, segmentaciones, el propio `CALCULATE`). Es lo
  que hace que la misma medida `[Venta Neta]` devuelva un número distinto en la celda
  de enero y en la celda de febrero de la misma matriz, sin que el autor de la medida
  escriba una condición de fecha en ningún lado.

`CALCULATE` es la función que **modifica el contexto de filtro** vigente. En
`Pedidos Entregados`, `CALCULATE(COUNTROWS(...), gold_fact_pedido[estado] = "ENTREGADO")`
no filtra "antes" ni "después": agrega esa condición al contexto de filtro ya existente
(el mes de la celda, el canal de la segmentación, lo que sea), y evalúa `COUNTROWS`
dentro de la intersección de todo eso. Esta es la razón por la que las mismas cinco
medidas, sin tocarlas, responden correctamente a PBI-07 Prueba 4 (filtrar por canal): el
filtro de canal ya estaba en el contexto antes de que `CALCULATE` añadiera el filtro de
estado, y DAX combina ambos con un AND implícito sobre la misma tabla de hechos.

### Qué hace `DATEADD` exactamente, y por qué necesita una tabla de fechas marcada

`DATEADD(gold_dim_fecha[fecha], -1, YEAR)` no resta un año a cada fecha de la tabla de
hechos directamente — opera sobre la **tabla de fechas**, y para saber qué cuenta como
"un año completo de calendario" (no 365 días fijos, sino el mismo rango de mes/día del
año anterior, respetando años bisiestos) necesita que el motor sepa cuál columna de
`gold_dim_fecha` es la fecha "real" y que esa columna sea continua, sin huecos ni
duplicados, cubriendo rangos completos. Marcar la tabla como tabla de fechas (PBI-03) es
lo que le dice al motor "esta tabla cumple esas condiciones, úsala para funciones de
inteligencia de tiempo". Sin ese marcado, `DATEADD` puede fallar directamente o —peor—
devolver un resultado silenciosamente incorrecto si el motor asume una relación que no
es la correcta.

### Por qué `tiene_datos` existe: el problema de comparar periodos desiguales

El calendario de `gold_dim_fecha` cubre años completos (enero 2025 a diciembre 2026)
porque `DATEADD` lo necesita para calcular "el mismo mes del año anterior" sin salirse
del rango de la tabla de fechas. Pero los **datos reales** terminan el 30 de septiembre
de 2026 (`fecha_max` en `config.py`). Si filtras "año 2026" sin ninguna corrección, DAX
suma honestamente los 9 meses de 2026 que sí tienen datos, y los compara contra los
**12 meses completos** de 2025 — una comparación real pero engañosa, porque un año
parcial nunca puede superar proporcionalmente a un año completo salvo que el crecimiento
sea extremo. La columna `tiene_datos` (`fecha_key <= MAX(fecha_pedido)`) es un filtro
que, aplicado dentro de `CALCULATETABLE` al calcular el periodo de comparación, excluye
del lado "actual" cualquier fecha futura sin dato — alineando los dos lados de la
comparación al mismo rango de calendario realmente poblado. El salto de +20,2 % a
+98,9 % en PBI-07 Prueba 2 no es un error de redondeo: es la diferencia entre comparar
peras con naranjas y comparar peras con peras.

### Import vs. DirectQuery vs. Direct Lake: qué cambia según la Ruta A o B de PBI-01

- **Import** (Ruta B, Power BI Desktop): copia los datos a la memoria del motor
  analítico (VertiPaq) en un formato columnar comprimido optimizado para DAX. Es el modo
  más rápido para consultas, pero necesita refrescarse para ver datos nuevos.
- **DirectQuery:** no copia nada; cada visual dispara una consulta SQL contra el origen
  en tiempo real. Siempre al día, pero cada interacción paga el costo de ir a la fuente.
- **Direct Lake** (Ruta A, vía Fabric): es el término medio descrito en
  [fabric_detallada.md](fabric_detallada.md#onelake-por-qué-direct-lake-no-importa-nada):
  lee los archivos Delta subyacentes directamente, sin copiar a otro almacenamiento,
  pero sin pagar el costo de una consulta SQL completa por cada interacción.

Las cinco medidas DAX se escriben igual en los tres modos: el lenguaje DAX no cambia,
cambia solo *dónde* y *cuándo* se materializan los datos que esas medidas consultan.

---

## PBI-01 · Conectar el modelo ⏱️ 30 min

(Mismas dos rutas que la versión corta: A desde Fabric Direct Lake, B desde Power BI
Desktop contra Databricks.)

**🧠 Por qué este proyecto recomienda la Ruta A:** si ya hiciste
[FAB-09](fabric_detallada.md#fab-09--modelo-semántico-direct-lake), las relaciones ya
están creadas y Direct Lake evita un paso de importación completo; la Ruta B es la
alternativa cuando no se validó Fabric, y usa el modo Import clásico, que es más
familiar si nunca trabajaste con Fabric.

**📎 Evidencia:** `evidencia/powerbi/01_conexion.png`.

---

## PBI-02 · Crear las relaciones ⏱️ 20 min

(Mismas cuatro relaciones de la versión corta: fecha, canal, categoría, cliente, todas
"varios a uno" con filtro cruzado simple.)

**🧠 Por qué "varios a uno" y "filtro cruzado simple" son la combinación correcta
aquí:** cada pedido (muchos) referencia exactamente un valor de cada dimensión (uno):
muchos pedidos comparten el mismo `canal_key`. "Filtro cruzado simple" significa que un
filtro en la dimensión (p. ej. seleccionar `APP` en `gold_dim_canal`) sí filtra los
hechos, pero un filtro en los hechos no vuelve a filtrar la dimensión — lo correcto para
un esquema en estrella clásico. Un filtro cruzado "bidireccional" aquí introduciría
ambigüedad cuando hay varias dimensiones relacionadas al mismo hecho (el problema
clásico de *ambiguity* en modelos con más de una relación bidireccional convergiendo).

**📎 Evidencia:** `evidencia/powerbi/02_relaciones.png`.

---

## PBI-03 · Marcar la tabla de fechas ⏱️ 10 min 🔴

(Mismos pasos: columna `fecha`, no `fecha_key`.)

**🧠 Por qué `fecha` y no `fecha_key`:** `fecha_key` es un entero (p. ej. `20260115`)
usado como clave de relación eficiente; `fecha` es la columna de tipo Fecha real. Las
funciones de inteligencia de tiempo de DAX (`DATEADD`, `SAMEPERIODLASTYEAR`, etc.)
operan sobre semántica de calendario (día, mes, año), que solo la columna de tipo Fecha
expresa correctamente — un entero como `20260115` no tiene aritmética de calendario
("un mes antes de 20260101" no es `20260101 - 100` en ningún sistema numérico sensato).

**📎 Evidencia:** `evidencia/powerbi/03_tabla_fechas.png`.

---

## PBI-04 · Crear la columna calculada `tiene_datos` ⏱️ 10 min 🔴

(Misma fórmula: `gold_dim_fecha[fecha_key] <= MAX(gold_fact_pedido[fecha_key])`.)

**🧠 Por qué es una columna calculada y no un filtro puesto directamente en la medida de
variación:** al ser una columna, puede reutilizarse dentro de `CALCULATETABLE` para
construir el conjunto de fechas de comparación ya acotado, en vez de repetir la
condición `<= MAX(...)` en cada medida que necesite esa misma restricción. También
permite, si hiciera falta, usarla directamente como filtro visual (una segmentación que
oculte fechas futuras sin dato) sin reescribir ninguna medida.

**🧠 Qué pasaría si se calculara al revés (`MAX` de la tabla de hechos sin la
dimensión):** el `MAX(gold_fact_pedido[fecha_key])` dentro de la definición de la
columna se evalúa en el contexto de fila de `gold_dim_fecha`, pero como no hay ningún
filtro activo sobre los hechos en ese momento (es una columna calculada, se evalúa una
vez al procesar el modelo, no por visual), `MAX` devuelve el máximo **global** de toda
la tabla de hechos — exactamente lo que se necesita: el último día con dato real en todo
el conjunto, sin importar qué muestre cada visual después.

**📎 Evidencia:** `evidencia/powerbi/04_tiene_datos.png`.

---

## PBI-05 · Instalar las cinco medidas ⏱️ 20 min

(Mismo DAX de la versión corta para las cinco medidas.)

**🧠 Qué hace cada medida, leída como DAX y no solo como fórmula:**

- **`Venta Neta`**: `SUMX` evalúa `valor_bruto - descuento` en **contexto de fila**
  (pedido por pedido) y luego suma; `CALCULATE` alrededor añade el filtro `estado =
  "ENTREGADO"` al **contexto de filtro**. El orden conceptual es: primero se decide qué
  filas son visibles (filtro + lo que venga de la visual), luego se recorre fila por
  fila con `SUMX`.
- **`Pedidos Entregados`**: mismo patrón pero con `COUNTROWS` en vez de `SUMX` — no
  necesita contexto de fila porque solo cuenta, no calcula una expresión por fila.
- **`Ticket Promedio`**: `DIVIDE` en vez de `/` — evita el error de división por cero
  cuando `Pedidos Entregados` es 0 (devuelve blanco en vez de `#ERROR`, lo que importa
  en PBI-07 Prueba 3, mes sin ventas en un canal).
- **`Venta Neta Mismo Mes Año Anterior`**: el `CALCULATETABLE` con `DATEADD(...)`
  construye, sobre la tabla de fechas, el conjunto de fechas "un año antes" del contexto
  de filtro actual, intersectado con `tiene_datos = TRUE()`; `CALCULATE` evalúa `[Venta
  Neta]` dentro de ese conjunto trasladado en vez del conjunto original.
- **`Variación vs Mismo Mes Año Anterior`**: usa variables (`VAR`) para evaluar
  `[Venta Neta]` y la medida anterior **una sola vez cada una** en este contexto, y
  `DIVIDE` de nuevo para que la ausencia de dato anterior (`ISBLANK`) produzca blanco —
  no cero — en la variación. Esto es lo que hace que PBI-07 Prueba 1 (año 2025) salga
  en blanco, no en `0 %`: hay una diferencia semántica real entre "no hubo cambio" (0 %)
  y "no hay con qué comparar" (blanco), y la medida la respeta explícitamente con la
  condición `NOT ISBLANK(previo)`.

**📎 Evidencia:** `evidencia/powerbi/05_medidas.png`.

---

## PBI-06 · Verificar contra los siete valores ⏱️ 45 min ⭐

(Misma matriz, mismas cifras de referencia por mes y por total que la versión corta.)

**🧠 Por qué estos valores salen de SQL y no de otro cálculo en Python/pandas:** porque
son el mismo cálculo que ya corre en `duckdb/01_ventas_recompra.sql` y sus equivalentes
(`sqlserver/`, `fabric/sql/`, `databricks/sql/`), descrito en
[CLAUDE.md](../../CLAUDE.md#arquitectura) como "el mismo SQL de venta neta/recompra en
cuatro dialectos que deben mantenerse alineados". Verificar DAX contra SQL, y no contra
otro DAX, es lo único que realmente prueba que la medida implementa la **misma regla de
negocio**, no solo una fórmula que "se ve razonable".

**📎 Evidencia:** `evidencia/powerbi/06_matriz.png`.

---

## PBI-07 · Las cuatro pruebas de borde ⏱️ 30 min

(Mismas cuatro pruebas de la versión corta. Para cada una, qué estás probando
realmente:)

### Prueba 1 · Año 2025 → variación vacía
**Qué prueba de verdad:** que `DIVIDE(..., ISBLANK check)` distingue "cero cambio" de
"sin dato para comparar". Si sale `0 %` en vez de blanco, la condición `NOT
ISBLANK(previo)` no está aplicándose — revisa si `previo` realmente queda `BLANK()`
cuando no hay fechas en el conjunto trasladado (lo esperado si `CALCULATETABLE` devuelve
una tabla vacía para 2024, fuera del rango del calendario).

### Prueba 2 · Año 2026 completo → +98,88 % 🔴
**Qué prueba de verdad:** que `tiene_datos` realmente participa en el cálculo del
periodo de comparación. Si sale +20,2 %, confirma primero con una tabla simple (sin la
medida) que la columna `tiene_datos` existe y tiene los valores correctos (True hasta
2026-09-30), y luego revisa que el `CALCULATETABLE` de `Venta Neta Mismo Mes Año
Anterior` referencia la columna con el nombre exacto de tabla (`gold_dim_fecha`, no
`dim_fecha`, si tu modelo usa el prefijo `gold_`).

### Prueba 3 · Mes sin ventas en un canal
**Qué prueba de verdad:** que el mes aparece con cero visible, no que desaparece de la
matriz. Esto depende de que la segmentación por canal **no** elimine filas de
`gold_dim_fecha` (la dimensión de fechas no se filtra por canal; solo los hechos sí), de
modo que la fila del mes siga presente en la matriz aunque la suma de ese mes para ese
canal sea cero.

### Prueba 4 · Filtro por canal
**Qué prueba de verdad:** que las cinco medidas, sin ninguna modificación, responden
correctamente a un filtro externo — exactamente el comportamiento de "contexto de
filtro" descrito en el recuadro de conceptos. Si alguna medida no responde al filtro de
canal (p. ej. siempre muestra el total general), es señal de que esa medida usa `ALL()`
o `REMOVEFILTERS()` sobre la dimensión de canal en algún punto, lo que no está en el DAX
documentado del proyecto.

### Prueba adicional sugerida · Mes futuro sin dato, sin filtro de año
**Haz:** sin ningún filtro de año, pon la matriz por mes hasta diciembre de 2026.
**✅ Debe salir:** los meses de octubre a diciembre de 2026 muestran `Venta Neta` en
blanco (no hay hechos ahí) y `Variación` también en blanco, nunca `-100 %`. Esto
distingue "no hay datos este periodo" de "la venta cayó a cero", un matiz que no cubre
ninguna de las cuatro pruebas originales pero que puede aparecer en un dashboard real.

**📎 Evidencia:** una captura por prueba.

---

## PBI-08 · Informe mínimo ⏱️ 20 min *(opcional)*

(Mismos elementos: gráfico de líneas por canal, tarjetas, segmentaciones.)

**🧠 Qué confirma visualmente este paso:** el hallazgo de negocio documentado en
[README.md](../../README.md#hallazgos-de-negocio) — APP subiendo y TIENDA cayendo entre
junio y septiembre de 2026 — debería ser visible a simple vista en el gráfico, sin
necesidad de leer ninguna cifra. Si no se ve, antes de dudar del hallazgo revisa que el
eje de fechas no esté agregado a nivel de año (que aplanaría la tendencia mensual).

**📎 Evidencia:** `evidencia/powerbi/08_informe.png`.

---

## PBI-09 · Conexión de solo lectura ⏱️ 20 min *(opcional)*

(Mismos pasos: usuario de solo lectura sobre el esquema Gold, reconfigurar la conexión.)

**🧠 Por qué este paso existe en el roadmap de Power BI y no solo en el de SQL Server:**
porque el PR original de la parte 3 (ver [docs/06_liderazgo.md](../06_liderazgo.md) y
`src/shared/reporte_ventas.py`) usaba un usuario `admin` con contraseña embebida en el
código para generar reportes — exactamente el patrón que una herramienta de BI con
credenciales de solo lectura está pensada para evitar. Repetirlo aquí cierra el mismo
círculo de higiene de acceso del lado de Power BI, no solo del lado del script Python.

**📎 Evidencia:** `evidencia/powerbi/09_lectura.png` con las credenciales tapadas.

---

## Glosario

| Término | Qué significa aquí |
|---|---|
| **Contexto de fila** | El "pedido actual" dentro de una función como `SUMX`; permite referenciar columnas de esa fila sin agregación |
| **Contexto de filtro** | El conjunto de filas visibles dado todo lo que filtra la visual/segmentación/`CALCULATE` en ese momento |
| **`CALCULATE`** | La función que modifica el contexto de filtro vigente añadiendo condiciones |
| **Tabla de fechas marcada** | Una tabla declarada ante el motor como calendario válido para funciones de inteligencia de tiempo; requiere continuidad sin huecos ni duplicados |
| **`DIVIDE`** | División segura en DAX que devuelve blanco (configurable) en vez de error cuando el divisor es cero |
| **Import / DirectQuery / Direct Lake** | Los tres modos de almacenamiento/consulta de un modelo semántico frente al origen de datos |
| **Filtro cruzado simple / bidireccional** | Cómo se propaga un filtro a través de una relación: solo en una dirección, o en ambas |

## Preguntas frecuentes de este bloque

**¿Por qué verificar DAX es "la tarea de mayor retorno" del roadmap completo?**
Porque de las cuatro afirmaciones débiles del proyecto, esta es la que más barato se
cierra (3 h) y la que más se pregunta en una sustentación de BI: "¿ejecutaste las
medidas en un motor real?" es casi siempre la primera pregunta sobre la parte de DAX.

**Si las cifras no coinciden, ¿cómo se distingue un error de DAX de un error de datos?**
Primero revisa si el modelo tiene el número correcto de filas en `gold_fact_pedido`
(19.270): si ya está mal ahí, el problema es de carga/conexión, no de DAX. Si las filas
son correctas pero la medida da otro número, revisa el DAX mismo contra la fórmula de
este documento, empezando por el filtro `estado = "ENTREGADO"`.

**¿Por qué la variación usa `VAR` en vez de llamar dos veces a `[Venta Neta]` y a
`[Venta Neta Mismo Mes Año Anterior]`?**
Por legibilidad y para evitar evaluar la misma expresión costosa dos veces si el motor
no la memoiza automáticamente en ese punto; funcionalmente, con el mismo contexto de
filtro, daría el mismo resultado sin `VAR`, pero `VAR` deja explícito que "actual" y
"previo" son dos valores fijos dentro de esta evaluación, no algo que cambia a mitad de
la fórmula.

## Para profundizar (documentación oficial)

- Contexto de fila y de filtro en DAX: <https://learn.microsoft.com/dax/>
- `CALCULATE`: <https://learn.microsoft.com/dax/calculate-function-dax>
- Funciones de inteligencia de tiempo (`DATEADD`, tabla de fechas): <https://learn.microsoft.com/dax/time-intelligence-functions-dax>
- Modos de almacenamiento (Import/DirectQuery/Direct Lake): <https://learn.microsoft.com/power-bi/connect-data/service-dataset-modes-understand>
