# Guía actualizada de trabajo

Consultar primero docs/ESTADO_IMPLEMENTACION.md, docs/PENDIENTES_ACTUALES.md, README.md y README_ETL.md.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

Solución a la prueba técnica "Andina Market" (Líder Técnico de Datos, BI y Automatización). La documentación está en español; mantén ese idioma en docs, comentarios y mensajes. `README.md` mapea cada punto de la prueba a su entregable y `README_ETL.md` detalla el ETL, las reglas de calidad y las limitaciones conocidas: léelos antes de cambiar reglas o definiciones de negocio.

## Comandos

Entorno: Python 3.12+ con versiones fijas en `requirements.txt`. El venv del proyecto es `finanzauto/`. Las pruebas con Spark se omiten solas si no se pueden correr (`tests/conftest.py::motivo_para_omitir_spark`): necesitan Java y, en Windows, Python 3.11 (con 3.12 se cae el worker de PySpark 3.5) y `HADOOP_HOME` para la prueba que escribe tablas.

```bash
pip install -r requirements.txt          # pandas, duckdb, pytest
pip install -r requirements-spark.txt    # opcional: pyspark 3.5.3 (necesita Java 17/21)
pip install -r requirements-ia.txt       # opcional: openai (cliente DeepSeek)

python scripts/cargar_datos.py --desde-cero   # borra data/warehouse.duckdb y data/bronze, recarga y verifica totales
python scripts/cargar_datos.py                # carga incremental (debe insertar 0 filas la 2ª vez)
python scripts/cargar_datos.py --recalcular-gold   # recalcula todos los días de Gold (tras cambiar la definición de venta)
python scripts/recalculo_independiente.py data/original   # cifras recalculadas con pandas, sin usar el ETL
python -m pytest -q                           # todas las pruebas (pytest.ini fija pythonpath=src/shared)
python -m pytest tests/test_rules.py::nombre_test -q   # una sola prueba
python scripts/catalogo_calidad.py            # regenera docs/02_catalogo_calidad.md
python src/shared/spark/build_notebook.py     # regenera fabric/notebooks/andina_etl_spark.ipynb
python src/shared/spark/verificar_paridad_real.py   # paridad DuckDB vs Spark con datos reales
python scripts/clasificar_tickets.py evaluar --metodo reglas   # --metodo llm requiere DEEPSEEK_API_KEY en .env.local o en el entorno; cuesta dinero
python scripts/clasificar_tickets.py reservada --metodo reglas --sintetica   # arnés de muestra reservada (IC, errores críticos, telemetría)
python scripts/ci_local.py                    # chequeos reproducibles sin datos originales; también valida que el notebook esté regenerado
python scripts/ci_spark.py                    # pruebas Spark; falla si alguna se omite
python scripts/verificar_entrega.py --raw data/original --caso   # evidencia aislada; no toca data/warehouse.duckdb
python scripts/qa_impresion.py --pdf          # auditoría de impresión de los HTML + PDF (necesita Chrome)
python scripts/importar_etiquetas.py propuestas --db data/warehouse.duckdb --version reglas-AAAA-MM-DD
python scripts/despachar_reporte.py --db data/warehouse.duckdb --dia 2026-09-30   # transporte de carpeta; no envía correo
python scripts/empaquetar.py                  # dist/andina-market.zip con manifiesto SHA-256

# Otros scripts de la carpeta, menos frecuentes pero parte del flujo documentado:
python scripts/previsualizar_reporte.py --db data/warehouse.duckdb --dia 2026-09-30   # vista previa HTML idempotente en disco, sin correo ni API
python scripts/cargar_modelo_sqlserver.py --db data/warehouse.duckdb   # por defecto solo muestra el plan; --aplicar --entorno-pruebas carga Gold a SQL Server de pruebas
python scripts/reconciliar_fuentes.py --raw data/original --db data/warehouse.duckdb   # diagnóstico de altas/bajas entre snapshots; nunca aplica bajas
python scripts/respaldo_local.py respaldar|restaurar <origen> <destino>   # respaldo/restauración en frío bajo el lock de la aplicación
python scripts/revision_etiquetas.py plantilla|auditar <archivo>   # plantilla y auditoría de anotación humana de tickets, sin generar decisiones
python scripts/generar_csv_sinteticos.py --out .local/sinteticos   # CSV con cada error sembrado, para validar plataforma sin datos personales
python scripts/ensayar_cambio.py              # ensayo aislado de un canal nuevo sobre copia temporal, sin tocar fuentes ni la base del caso
```

Ejecutar Spark localmente en Windows: el venv `.venv/` es Python 3.11 y tiene PySpark; `finanzauto/` es 3.12 y no sirve para Spark. Las pruebas que escriben tablas (`test_sql_spark.py`) siguen omitiéndose sin `HADOOP_HOME`.

```bash
PYSPARK_PYTHON=... PYSPARK_DRIVER_PYTHON=... SPARK_LOCAL_IP=127.0.0.1   ./.venv/Scripts/python.exe -m pytest tests/test_spark_paridad.py tests/test_spark_extensiones.py -q
```

Los CSV de entrada deben estar en `data/original/` (no se versionan). `cargar_datos.py` termina con `CARGA CORRECTA` si coinciden las cifras de referencia (6.040 clientes, 19.270 pedidos, 20.124 pagos, 7.925 filas Gold, venta neta 14.177.333.600); si cambias reglas o datos, esas constantes (`ESPERADO`, `VENTA_NETA_ESPERADA` en el script) y los números en los docs deben actualizarse.

## Arquitectura

Pipeline medallion con **dos implementaciones del mismo diseño** que deben mantenerse en paridad:

- **Local (DuckDB)**, `src/shared/andina_etl/`: `config.py` (parámetros de negocio: rango de fechas, estados que cuentan como venta, mapa de canales), `rules.py` (reglas de calidad), `bronze.py` (CSV → Parquet crudo, todo como texto, versionado por sha256 en `data/bronze/<tabla>/ingest_date=.../`), `store.py` (esquema DuckDB Silver/Gold, upserts por `row_hash`, vistas como `v_cliente_maestro`, `refrescar_venta_neta`), `pipeline.py` (orquestación), `cli.py` (`python -m andina_etl`).
- **Spark/Delta (Fabric o Databricks)**, `src/shared/spark/rules_spark.py` (reglas de fila) + `extensiones_spark.py` (soporte, contratos, estrella, incidencias, publicación) + notebook generado en `fabric/notebooks/`. El notebook es **generado** por `build_notebook.py`; edita el generador, no el `.ipynb` (`ci_local.py` falla si están desincronizados). Cualquier cambio en `rules.py` debe replicarse en `rules_spark.py` (`tests/test_spark_paridad.py`) y cualquier cambio en `tickets.py`, `star.py`, `contracts.py` u `operations.py` en `extensiones_spark.py` (`tests/test_spark_extensiones.py`, que compara la estrella fila a fila contra DuckDB).

En Delta no hay transacción entre tablas: la consistencia se logra escribiendo los hechos con `run_id` y moviendo el puntero `publicacion_actual` solo si concilian; los consumidores leen las vistas `v_fact_*`. Las funciones con prefijo `delta_` usan `MERGE`/`UPDATE` y **no se han ejecutado** (ver docs/08_traslado_delta.md).

Flujo: CSV → Bronze (Parquet inmutable) → Silver (siempre leído desde Bronze, nunca del CSV) → `cuarentena` (una fila por registro y regla violada, con la fila original en JSON) → Gold `gold_venta_neta_diaria` (recalculado desde Silver solo para los días tocados). Idempotencia vía `row_hash`; pagos incrementales con watermark sobre `fecha_carga` más `lookback_dias`, pero los pagos en cuarentena por `PAGO_HUERFANO`/`PEDIDO_EN_CUARENTENA` se releen siempre (`store.pagos_pendientes`). Cada corrida de `pipeline.ejecutar` es una transacción DuckDB; los registros ya cargados que pasan a inválidos se retiran de Silver (`store.retirar`) y se recalcula su día. El notebook Delta replica esto; en lugar de la transacción usa el puntero de publicación descrito arriba, y `RECALCULAR_GOLD` para rehacer todos los días tras una caída.

Decisiones de negocio que atraviesan varios archivos (SQL, DAX, ETL, docs): venta neta = `valor_bruto − descuento` de pedidos `ENTREGADO`, atribuida a `fecha_pedido`; rango válido 2025-01-01 a 2026-09-30; clientes con el mismo documento son una persona. Cambiar una de ellas implica tocar `config.py`/`rules.py`, `store.py`, las cuatro variantes de SQL y `fabric/semantic_model/medidas.dax`.

El mismo SQL de venta neta/recompra existe en cuatro dialectos que deben mantenerse alineados: `sqlserver/` (T-SQL), `duckdb/`, `fabric/sql/`, `databricks/sql/`; la plantilla de Spark está en `src/shared/spark/sql/`.

Etiquetas de tipo de caso (`andina_etl/etiquetas.py`): se importan por lote versionado con su origen. `gold.fact_ticket.tipo_caso` **solo** admite etiquetas en estado `REVISADA` (origen humano, dos anotadores y motivo); la salida de un clasificador va a `tipo_caso_propuesto`. La asociación es por hash del texto normalizado, que `tickets.py` guarda en `silver_tickets.texto_hash`. No romper esa separación: es la garantía de que una propuesta no se publique como validada.

Otras piezas independientes: `src/shared/reporte_ventas.py` (versión corregida del PR de la parte 3.1), `src/shared/tickets_ia/` (clasificación de tickets: reglas como línea base y `ClasificadorLLM` contra DeepSeek), `src/shared/tickets_ia/evaluacion.py` (arnés de muestra reservada: intervalos de Wilson, errores críticos, fugas, telemetría), `src/shared/reporte_envio.py` (transporte del reporte: duplicados por hash de contenido, reintento solo ante fallo transitorio; nunca envía sin autorización explícita), `sqlserver/optimizacion/` (experimento con SQLite), `docs/` (entregables escritos; los PDF se generan desde el HTML con `scripts/qa_impresion.py --pdf`).

Al tocar el CSS de impresión de los HTML de `docs/`, volver a correr `python scripts/qa_impresion.py --pdf`: regenera los PDF y la evidencia, y `tests/test_impresion.py` comprueba que ninguna página quede vacía o con una línea suelta.

## Qué no está verificado

T-SQL, DDL, DAX y celdas Delta del notebook (MERGE, DELETE, DESCRIBE HISTORY, rutas de Lakehouse/Volumes) **no se han ejecutado** en sus plataformas. El transporte SMTP del reporte tampoco. La API de DeepSeek sí se ejecutó (Flash y V4 Pro, clave en `.env.local`); las pruebas automáticas no la llaman, usan una función falsa. No afirmes lo contrario en docs ni en respuestas; `docs/ESTADO_IMPLEMENTACION.md` es la fuente de verdad del estado y debe actualizarse si eso cambia, junto con `docs/PENDIENTES_ACTUALES.md`.

## Notas

- `python -m andina_etl` requiere `PYTHONPATH=src/shared`; el comando soportado es `scripts/cargar_datos.py`.
- El directorio es el repositorio Git privado mcoy2025ia/andina-market.
