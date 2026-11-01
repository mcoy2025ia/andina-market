# Andina Market · Prueba técnica de datos, BI y automatización

Este repositorio contiene la solución técnica del caso. Estado actual: **ETL de pedidos y pagos con capa Bronze en Parquet, calidad de datos, cuarentena y venta neta diaria** (Parte 1, punto 3), con su modelo de datos, pruebas y una versión PySpark + Delta para Fabric o Databricks. El resto de la prueba (SQL, DAX, optimización, arquitectura, liderazgo, IA) está mapeado en `README.md`.

## Uso de IA generativa

Se usó Claude (Anthropic) como asistente para diseñar y escribir parte del código, las pruebas y esta documentación. Cada decisión de negocio (definición de venta neta, tratamiento de duplicados, rango de fechas) está escrita abajo para poder discutirla y modificarla en la sustentación.

## Cómo ejecutarlo desde cero

Requiere Python 3.12 o superior (es la versión con la que se probó). No necesita SQL Server: el ETL usa DuckDB, un archivo local.

```bash
python -m venv finanzauto
source finanzauto/bin/activate       # Windows (Git Bash): source finanzauto/Scripts/activate
pip install -r requirements.txt

# descomprimir datos_prueba_tecnica.zip en data/original/ (clientes.csv, pedidos.csv, pagos.csv, tickets_soporte.csv)

python scripts/cargar_datos.py --desde-cero   # CSV -> Bronze (Parquet) -> Silver -> Gold y verifica totales
python scripts/cargar_datos.py                # segunda vez: 0 insertados, 0 cuarentena nueva, Bronze "ya existía"
python -m pytest -q                           # 85 pruebas sin Spark (las de Spark se omiten si no se pueden correr)
```

También existe `python -m andina_etl`, que imprime el resumen por tabla y regla; desde la raíz necesita `PYTHONPATH=src/shared`. Opciones: `--raw`, `--db`, `--bronze`, `--fecha-min`, `--fecha-max`, `--lookback-dias`, `--recalcular-gold` (ver `--help`).

Para correr además la paridad con Spark: `pip install -r requirements-spark.txt` (necesita Java 17 o 21; en Windows, Python 3.11, porque con 3.12 se cae el *worker* de Python, y `HADOOP_HOME` con `winutils.exe` para la prueba que escribe tablas) y
`python src/shared/spark/verificar_paridad_real.py`.

Para consultar el resultado:

```bash
python -c "import duckdb; print(duckdb.connect('data/warehouse.duckdb', read_only=True).sql('SELECT * FROM gold_venta_neta_diaria ORDER BY fecha LIMIT 10'))"
```

## Formatos y herramientas: qué se decidió y por qué

**El CSV es solo el contrato de entrada.** El caso entrega cuatro CSV; lo que el ETL guarda no es CSV. Cada capa tiene su formato:

| Capa | Formato | Por qué |
|---|---|---|
| Fuente | CSV (así lo entrega el caso) | En producción serían APIs y SQL Server, no archivos |
| Bronze | Parquet, todo como texto, con columnas de trazabilidad | Copia cruda e inmutable; conserva tipos y esquema sin interpretarlos |
| Silver y Gold | DuckDB local; Delta en Fabric o Databricks | Delta agrega MERGE, transacciones e historial, que son lo que hace idempotente la carga |

**Medición con datos reales y a escala** (DuckDB, una sola máquina; `pedidos.csv`):

| | CSV | Parquet zstd |
|---|---|---|
| 19.734 filas reales: tamaño | 1,7 MB | 0,4 MB |
| 19.734 filas reales: agregado mensual | 86 ms | 6,5 ms |
| 4,9 M filas: tamaño | 445 MB | 57 MB |
| 4,9 M filas: agregado mensual | 1.667 ms | 181 ms |
| 4,9 M filas: consulta de un solo mes | 1.263 ms | 17 ms |

Con los datos del caso la diferencia de tiempo no se nota (ambos responden al instante), así que la razón para usar Parquet y Delta aquí son los tipos, el esquema y el MERGE, no la velocidad. La versión de 4,9 M filas repite filas del original, por lo que la compresión probablemente esté inflada; y la consulta de un mes es rápida porque el archivo se escribió ordenado por fecha. Extrapolando de forma lineal a 50 millones de pedidos, serían unos 4,5 GB en CSV contra unos 0,6 GB en Parquet.

**Cuándo vale la pena pasar de CSV a Parquet o Delta** (criterios generales, no medidos aquí):

- Desde el primer día en Bronze, porque conservar tipos y esquema no cuesta nada.
- Cuando se necesita MERGE, historial o transacciones: ahí el paso es a Delta.
- Desde cientos de MB o millones de filas por tabla, o con varias consultas sobre la misma tabla.
- En la nube, porque se paga por datos leídos y el pruning por fecha reduce el costo.
- El CSV se queda para el aterrizaje como evidencia, el intercambio con terceros y lo que el negocio abre en Excel.

**Dos implementaciones del mismo proceso:**

| | Local | Fabric o Databricks |
|---|---|---|
| Código | `src/shared/andina_etl/` (Python + DuckDB) | `fabric/notebooks/andina_etl_spark.ipynb` (PySpark + Delta) |
| Reglas | `andina_etl/rules.py` | `src/shared/spark/rules_spark.py` |
| Para qué | Correr y modificar en cualquier máquina, sin infraestructura | Mostrar que el mismo diseño corre en una plataforma Spark |

La paridad entre ambas está comprobada: con Spark 3.5 local y ANSI activado, las reglas dan los mismos conteos por regla, los mismos registros válidos, el mismo hash de fila y la misma venta neta sobre los datos reales (`tests/test_spark_paridad.py` y `spark/verificar_paridad_real.py`). **No se ejecutó en Fabric ni en Databricks:** el `MERGE INTO`, el `DELETE`, `DESCRIBE HISTORY` y las rutas propias de cada plataforma se escribieron con sintaxis estándar de Delta, pero no se probaron. El notebook termina con una celda que compara contra las cifras del ETL local.

Se regenera con `python src/shared/spark/build_notebook.py`.

## Decisiones de negocio

| Decisión | Qué se hizo | Dónde cambiarla |
|---|---|---|
| Venta neta | `valor_bruto - descuento` de pedidos en estado ENTREGADO. DEVUELTO y CANCELADO no son venta | `ESTADO_VENTA` en `config.py` |
| Fecha de la venta | `fecha_pedido` (no `fecha_entrega`) | `refrescar_venta_neta` en `store.py` |
| Rango válido | `fecha_pedido` entre 2025-01-01 y 2026-09-30 | `Config` o `--fecha-min/--fecha-max` |
| Cliente inexistente | La venta se conserva y se marca `flag_cliente_desconocido` (descartarla subestimaría la venta) | `validar_pedidos` |
| Mismo documento, dos `id_cliente` | Se tratan como la misma persona: vista `v_cliente_maestro` | `ESQUEMA` en `store.py` |
| Duplicados | Gana el registro que ya está en Silver; si ninguno está, el de menor id | `_marcar_duplicados` |

## Reglas de calidad

Cada registro que incumple una regla va a la tabla `cuarentena` con la regla violada y la fila original completa en JSON. Una fila por (registro, regla); para contar registros afectados usar `COUNT(DISTINCT id_registro)`.

| Tabla | Regla | Condición |
|---|---|---|
| clientes | `ID_CLIENTE_NULO`, `FECHA_REGISTRO_INVALIDA` | sin id o con fecha de registro ilegible |
| clientes | `ID_CLIENTE_DUPLICADO` | el mismo id aparece dos veces (se conserva la primera) |
| pedidos | `ID_PEDIDO_NULO`, `ID_PEDIDO_DUPLICADO` | sin id, o el mismo id aparece más de una vez en el archivo (van todas las copias: no se sabe cuál es la buena) |
| pedidos | `CANAL_DESCONOCIDO` | el canal no está en el mapa de normalización |
| pedidos | `ESTADO_INVALIDO` | estado distinto de ENTREGADO, DEVUELTO o CANCELADO |
| pedidos | `FECHA_PEDIDO_INVALIDA`, `FECHA_FUERA_DE_RANGO` | no es fecha, o está fuera del rango |
| pedidos | `VALOR_BRUTO_NO_POSITIVO` | valor bruto menor o igual a cero |
| pedidos | `DESCUENTO_INVALIDO` | descuento negativo o mayor que el valor bruto |
| pedidos | `ENTREGADO_SIN_FECHA`, `ENTREGA_ANTERIOR_A_PEDIDO` | incoherencia entre estado y fechas |
| pedidos | `DUPLICADO_LOGICO` | mismo cliente, fecha-hora, valor bruto y categoría con otro `id_pedido` |
| pagos | `ID_PAGO_NULO`, `ID_PEDIDO_NULO`, `ID_PAGO_DUPLICADO` | sin id de pago o de pedido, o el mismo id de pago repetido en el archivo |
| pagos | `FECHA_PAGO_INVALIDA`, `FECHA_CARGA_INVALIDA`, `VALOR_INVALIDO`, `MEDIO_PAGO_INVALIDO` | formato o valor inválido |
| pagos | `PAGO_HUERFANO` | el pedido no existe |
| pagos | `PEDIDO_EN_CUARENTENA` | el pedido existe pero fue rechazado |
| pagos | `PAGO_ANTERIOR_A_PEDIDO` | el pago es anterior al pedido |
| pagos | `DUPLICADO_LOGICO` | mismo pedido, fecha, valor y medio, aunque la fecha venga en otro formato |

Además se normalizan el canal (8 variantes sucias a WEB, APP o TIENDA), la fecha de pago (`yyyy-mm-dd` y `dd/mm/yyyy` con formato explícito) y el documento del cliente (solo dígitos, sin ceros a la izquierda).

## Resultados sobre los datos del caso

| | Leídos | Válidos | Registros en cuarentena |
|---|---|---|---|
| pedidos | 19.734 | 19.270 | 464 |
| pagos | 20.883 | 20.124 | 759 |
| clientes | 6.040 | 6.040 | 0 |

Venta neta total: 7.925 filas diarias (día, canal, categoría), 16.855 pedidos entregados, COP 14.177.333.600. Verificado de forma independiente con pandas sobre los CSV crudos (`scripts/recalculo_independiente.py`, que no usa el código del ETL).

Hallazgos que conviene mencionar:

- 40 clientes aparecen dos veces con el mismo documento, nombre, ciudad y fecha de registro. Solo se ven al limpiar el formato del documento.
- Comparando la fecha como texto se ven 309 pagos duplicados; normalizando los dos formatos de fecha son 350 (41 más), porque el mismo pago llega con la fecha escrita distinto. Son conteos sobre el archivo completo; el catálogo da 344 porque cuenta solo entre los pagos que pasaron las demás reglas.
- 345 pagos pertenecen a pedidos rechazados; casi la mitad (167) son pedidos duplicados lógicos.
- 60 pedidos apuntan a clientes que no existen; se conservan marcados.

## Cómo se garantiza idempotencia e incremental

- **Bronze.** Cada versión distinta de un archivo de origen (por sha256) se guarda una sola vez en `data/bronze/<tabla>/ingest_date=AAAA-MM-DD/`; el mismo archivo no escribe nada nuevo y los Parquet ya escritos no se modifican. Silver siempre se construye leyendo Bronze, nunca el CSV.
- **Idempotencia.** Cada registro tiene un `row_hash` calculado sobre los datos tal como llegan. Silver solo escribe lo nuevo o lo que cambió de hash; la segunda ejecución reporta 0 insertados y 0 actualizados. La cuarentena tiene llave (tabla, id, regla, hash), así que no se duplica. La venta diaria se recalcula desde Silver para los días tocados, por lo que depende solo de Silver.
- **Pagos incrementales.** Se lee desde `watermark - lookback_dias` sobre `fecha_carga`; el watermark avanza al máximo `fecha_carga` leído. La ventana absorbe cargas tardías sin reprocesar el histórico.
- **Pedidos incrementales.** La fuente no trae fecha de carga ni de modificación. Se lee el archivo completo pero solo se escribe lo nuevo o cambiado (por hash). Con una columna `updated_at` en la fuente se cambiaría por watermark.
- **Recálculo.** Si un pedido cambia de estado o de fecha, se recalculan su día nuevo y su día anterior. `--recalcular-gold` recalcula todos los días (tras cambiar la definición de venta).
- **Atomicidad.** Cada corrida es una sola transacción de DuckDB: si falla a la mitad no queda Silver actualizado con Gold viejo, y basta con volver a ejecutarla. El notebook de Delta no tiene transacciones entre tablas: tras una falla se reejecuta con `RECALCULAR_GOLD = True`.
- **Registros que pasan a inválidos.** Si un pedido o pago ya cargado cambia en la fuente (o cambia una regla) y deja de ser válido, sale de Silver y se recalcula su día; los pagos de ese pedido también salen.
- **Pagos que esperan a su pedido.** Los pagos en cuarentena por `PAGO_HUERFANO` o `PEDIDO_EN_CUARENTENA` se releen en cada corrida aunque estén fuera de la ventana, para cargarlos cuando llegue o se corrija el pedido.

## Limitaciones conocidas

- Un pedido borrado de la fuente sigue en Silver: el archivo no trae marcas de borrado.
- Un pago ya cargado que se corrige en la fuente con una `fecha_carga` fuera de la ventana no se relee (en los datos el desfase máximo entre pago y carga es de 2 días, menor que el lookback de 3).
- `flag_cliente_desconocido` se calcula al escribir el pedido: si el cliente llega en una carga posterior, el flag no se actualiza hasta que el pedido cambie.
- Si un duplicado llega en una carga posterior con un id menor que el original, gana el que ya estaba en Silver (decisión deliberada, estable entre recargas).
- El ETL no corta en la primera falla de un archivo: lo inválido va a cuarentena y el resto sigue. Los umbrales de alerta (por ejemplo, % de cuarentena) se definen en la arquitectura, no aquí.
- `sqlserver/ddl_tsql.sql` no se ejecutó contra un SQL Server real.
- El notebook de Spark no se ejecutó en Fabric ni en Databricks (ver arriba qué sí está probado).
- En el notebook, el hash del archivo de origen se calcula con `binaryFile`, que carga el archivo completo en memoria: sirve para estos tamaños, no para archivos de varios GB.

## Estructura

```
src/shared/andina_etl/   config.py, rules.py (calidad), bronze.py, store.py (DuckDB), pipeline.py, cli.py
src/shared/spark/        rules_spark.py (reglas PySpark), build_notebook.py, verificar_paridad_real.py
fabric/notebooks/        andina_etl_spark.ipynb (Fabric o Databricks)
scripts/                 cargar_datos.py, catalogo_calidad.py, recalculo_independiente.py
tests/                   reglas, Bronze, idempotencia, incremental, caídas, recálculo, paridad con Spark
sqlserver/ddl_tsql.sql   modelo en SQL Server o Fabric Warehouse
data/original/     CSV de origen (no se versionan); data/bronze y la base se generan al correr
```

## Estado

Todos los puntos de la prueba están entregados; `README.md` dice dónde está cada uno y qué se probó y qué no.
