"""Genera notebooks/andina_etl_spark.ipynb (Fabric o Databricks) a partir de spark/rules_spark.py.

Uso: python spark/build_notebook.py
El notebook lleva las reglas pegadas en una celda para que no dependa de subir archivos .py.
"""
import json
import re
import uuid
import hashlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
AQUI = Path(__file__).resolve().parent
REGLAS = (AQUI / "rules_spark.py").read_text(encoding="utf-8")
# En el notebook las reglas ya están en el espacio de nombres de la celda anterior,
# así que el import entre módulos sobra (y fallaría: no hay archivos .py que subir).
EXTENSIONES = re.sub(r"^from rules_spark import .*$", "",
                     (AQUI / "extensiones_spark.py").read_text(encoding="utf-8"), flags=re.M)

INTRO = """# Andina Market · ETL en PySpark + Delta (Fabric o Databricks)

Mismo proceso que `python -m andina_etl`, escrito para Spark: **CSV → Bronze (Parquet crudo) → Silver (Delta, MERGE idempotente) → cuarentena → venta neta diaria (Delta)**.

**Cómo ejecutarlo**

- **Fabric:** crea un Lakehouse, sube los 4 CSV a `Files/andina/raw/`, adjunta el Lakehouse al notebook y ejecuta todas las celdas.
- **Databricks:** crea el catálogo/esquema `andina.datos` y un Volume con los CSV, cambia `PLATAFORMA` en la celda 1 y ejecuta todas las celdas.
- **Idempotencia:** vuelve a ejecutar todo. La celda de resumen debe mostrar 0 insertados y 0 actualizados.
- **Verificación:** la última celda compara contra las cifras del ETL local (19.270 pedidos y 20.124 pagos válidos; venta neta 14.177.333.600).

**Qué está probado y qué no**

- Probado con PySpark 3.5 local y ANSI activado: las reglas de calidad (celda 2) dan **los mismos conteos por regla, los mismos válidos y la misma venta neta** que la versión pandas/DuckDB sobre los datos reales.
- **No probado:** `MERGE INTO`, `DELETE` y `DESCRIBE HISTORY` de Delta, las rutas de Fabric/Databricks y la lectura `binaryFile`. Se escribieron con la sintaxis estándar de Delta, pero no se ejecutaron en ninguna plataforma. Si algo falla, probablemente sea ahí.
- **Caídas a mitad de corrida:** Delta no tiene transacciones entre tablas (la versión DuckDB sí usa una). Si el notebook falla después de escribir Silver y antes de Gold, vuelve a ejecutarlo con `RECALCULAR_GOLD = True` en la celda 1. Lo mismo tras cambiar la definición de venta.
"""

CONFIG = '''# === 1. Configuración: lo único que cambia entre Fabric y Databricks ===
import uuid
import hashlib
from datetime import datetime
from pyspark.sql import functions as F

PLATAFORMA = "fabric"            # "fabric" o "databricks"
FECHA_MIN, FECHA_MAX = "2025-01-01", "2026-09-30"   # rango válido de fecha_pedido
LOOKBACK_DIAS = 3                # ventana de reproceso de pagos sobre fecha_carga
ESTADO_VENTA = "ENTREGADO"       # lo único que cuenta como venta
RECALCULAR_GOLD = False          # True: recalcula todos los días (tras una caída o un cambio de definición)

if PLATAFORMA == "fabric":
    # Lakehouse por defecto adjunto al notebook
    RAW, BRONZE = "Files/andina/raw", "Files/andina/bronze"
    def T(nombre):               # tablas del Lakehouse: silver_pedidos, cuarentena, ...
        return nombre
else:
    # Unity Catalog + Volumes
    RAW, BRONZE = "/Volumes/andina/datos/raw", "/Volumes/andina/datos/bronze"
    def T(nombre):
        return f"andina.datos.{nombre}"
'''

CONTRATOS_CELDA = '''# === 5. Contrato de archivo: un CSV inválido detiene la corrida, no sus filas ===
# Si la cabecera cambió, lo que viene debajo no significa lo que el proceso cree.
# Por eso esto corre antes de aterrizar nada en Bronze.
contratos = {}
for _tabla in ("clientes", "pedidos", "pagos", "tickets_soporte"):
    try:
        contratos[_tabla] = verificar_contrato(spark, f"{RAW}/{_tabla}.csv", _tabla)
    except AnalysisException:
        if _tabla == "tickets_soporte":      # soporte es opcional
            contratos[_tabla] = None
            continue
        raise
for _tabla, _info in contratos.items():
    print(f"{_tabla:16}", "ausente (opcional)" if _info is None else
          f"{_info['filas']:>7} filas, columnas extra: {_info['extras'] or 'ninguna'}")
'''

DDL = '''# === 4. Tablas Delta (se crean una sola vez) ===
ddl = {
    "silver_clientes": """id_cliente STRING, nombre STRING, documento_original STRING, documento_limpio STRING,
        ciudad STRING, canal_registro STRING, fecha_registro DATE, cohorte_registro DATE,
        row_hash STRING, ingested_at TIMESTAMP""",
    "silver_pedidos": """id_pedido STRING, id_cliente STRING, fecha_pedido TIMESTAMP, fecha_pedido_dia DATE,
        canal STRING, categoria STRING, valor_bruto BIGINT, descuento BIGINT, valor_neto BIGINT,
        estado STRING, fecha_entrega DATE, flag_cliente_desconocido BOOLEAN, hash_negocio STRING,
        row_hash STRING, ingested_at TIMESTAMP""",
    "silver_pagos": """id_pago STRING, id_pedido STRING, fecha_pago DATE, valor BIGINT, es_reembolso BOOLEAN,
        medio_pago STRING, fecha_carga DATE, hash_negocio STRING, row_hash STRING, ingested_at TIMESTAMP""",
    "cuarentena": """tabla_origen STRING, id_registro STRING, regla_violada STRING, row_hash STRING,
        registro_json STRING, run_id STRING, fecha_proceso TIMESTAMP""",
    "etl_watermark": "tabla STRING, ultimo_valor DATE, ultimo_run_id STRING, actualizado_en TIMESTAMP",
    "bronze_manifest": "tabla STRING, sha256 STRING, ruta STRING, filas BIGINT, run_id STRING, ingested_at TIMESTAMP",
    "gold_venta_neta_diaria": """fecha DATE, canal STRING, categoria STRING, num_pedidos BIGINT,
        venta_bruta BIGINT, descuento BIGINT, venta_neta BIGINT""",
}
ddl.update(DDL_EXTENSIONES)          # soporte, estrella, incidencias y publicación
for tabla, columnas in ddl.items():
    spark.sql(f"CREATE TABLE IF NOT EXISTS {T(tabla)} ({columnas}) USING DELTA")
spark.sql(f"CREATE OR REPLACE VIEW {T('v_cliente_maestro')} AS " + sql_cliente_maestro(T))
spark.sql(f"CREATE OR REPLACE VIEW {T('v_etiqueta_vigente')} AS " + sql_etiqueta_vigente(T))
'''

BRONZE_CELDA = '''# === 6. Bronze: copia cruda en Parquet, inmutable e idempotente ===
from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

SCHEMA_MANIFEST = StructType([
    StructField("tabla", StringType()), StructField("sha256", StringType()), StructField("ruta", StringType()),
    StructField("filas", LongType()), StructField("run_id", StringType()), StructField("ingested_at", TimestampType())])


def aterrizar(tabla, run_id):
    """Aterriza <tabla>.csv en Bronze si su contenido (sha256) es nuevo; devuelve lo que hay en Bronze.
    El mismo archivo dos veces no escribe nada; uno distinto crea un snapshot nuevo y no toca el anterior."""
    origen = f"{RAW}/{tabla}.csv"
    sha = spark.read.format("binaryFile").load(origen).select(F.sha2("content", 256)).first()[0]
    previo = (spark.table(T("bronze_manifest"))
              .filter((F.col("tabla") == tabla) & (F.col("sha256") == sha)).select("ruta").collect())
    if previo:
        ruta, nuevo = previo[0][0], False
    else:
        # todo como texto: tipar y validar es trabajo de Silver, no de Bronze
        df = spark.read.csv(origen, header=True, inferSchema=False)
        ahora = datetime.now()
        ruta = f"{BRONZE}/{tabla}/ingest_date={ahora:%Y-%m-%d}/{tabla}_{sha[:12]}"
        (df.withColumn("_ingested_at", F.lit(ahora)).withColumn("_run_id", F.lit(run_id))
           .withColumn("_source_file", F.lit(f"{tabla}.csv")).withColumn("_source_sha256", F.lit(sha))
           .write.mode("errorifexists").parquet(ruta))
        filas = spark.read.parquet(ruta).count()
        (spark.createDataFrame([(tabla, sha, ruta, filas, run_id, ahora)], SCHEMA_MANIFEST)
              .write.mode("append").saveAsTable(T("bronze_manifest")))
        nuevo = True
    leido = spark.read.parquet(ruta)
    leido = leido.select(*[c for c in leido.columns if not c.startswith("_")])
    return leido, nuevo
'''

PIPELINE = '''# === 7. Clientes -> pedidos -> pagos (cada paso es idempotente por sí mismo) ===
run_id, inicio = str(uuid.uuid4()), datetime.now()
resumen = {}


def metricas_ultimo_merge(tabla):
    m = spark.sql(f"DESCRIBE HISTORY {T(tabla)} LIMIT 1").select("operationMetrics").first()[0]
    return int(m.get("numTargetRowsInserted", 0)), int(m.get("numTargetRowsUpdated", 0))


def merge_silver(df, tabla, clave):
    """Inserta lo nuevo y reemplaza lo que cambió de row_hash; lo idéntico no se toca."""
    df.withColumn("ingested_at", F.current_timestamp()).createOrReplaceTempView("stg")
    spark.sql(f"""
        MERGE INTO {T(tabla)} t USING stg s ON t.{clave} = s.{clave}
        WHEN MATCHED AND t.row_hash <> s.row_hash THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""")
    return metricas_ultimo_merge(tabla)


def merge_cuarentena(df):
    """Una fila por (tabla, registro, regla, contenido). Reprocesar el mismo archivo no duplica filas."""
    (df.dropDuplicates(["tabla_origen", "id_registro", "regla_violada", "row_hash"])
       .withColumn("run_id", F.lit(run_id)).withColumn("fecha_proceso", F.current_timestamp())
       .createOrReplaceTempView("stg_q"))
    spark.sql(f"""
        MERGE INTO {T("cuarentena")} t USING stg_q s
        ON t.tabla_origen = s.tabla_origen AND t.id_registro = s.id_registro
           AND t.regla_violada = s.regla_violada AND t.row_hash = s.row_hash
        WHEN NOT MATCHED THEN INSERT *""")
    return int(spark.sql(f"DESCRIBE HISTORY {T('cuarentena')} LIMIT 1")
               .select("operationMetrics").first()[0].get("numTargetRowsInserted", 0))


# ---- clientes
cli_raw, nuevo_b = aterrizar("clientes", run_id)
cli_ok, cli_q = validar_clientes(cli_raw)
ins, upd = merge_silver(cli_ok, "silver_clientes", "id_cliente")
resumen["clientes"] = dict(insertados=ins, actualizados=upd, cuarentena_nueva=merge_cuarentena(cli_q), bronze_nuevo=nuevo_b)

# ---- pedidos: la fuente no trae fecha de carga, así que el incremental es por contenido (row_hash)
ped_raw, nuevo_b = aterrizar("pedidos", run_id)
negocio = (spark.table(T("silver_pedidos")).filter(F.col("hash_negocio").isNotNull())
           .groupBy("hash_negocio").agg(F.min("id_pedido").alias("id_pedido")))
ped_ok, ped_q = validar_pedidos(ped_raw, FECHA_MIN, FECHA_MAX, spark.table(T("silver_clientes")).select("id_cliente"), negocio)
ped_ok = ped_ok.cache()

# Días de venta a recalcular: el día nuevo de cada fila escrita y el día anterior si ya existía
previo = spark.table(T("silver_pedidos")).select("id_pedido", F.col("row_hash").alias("h_prev"), F.col("fecha_pedido_dia").alias("dia_prev"))
cambios = ped_ok.join(previo, "id_pedido", "left").filter(F.col("h_prev").isNull() | (F.col("h_prev") != F.col("row_hash")))
dias = sorted({r[0] for r in cambios.select("fecha_pedido_dia").union(cambios.select("dia_prev")).distinct().collect() if r[0]})


def rechazados(q, ok, clave):
    """Ids que fueron a cuarentena en esta corrida y no quedaron entre los válidos. Se recogen
    antes del MERGE: Spark es perezoso y, si no, se recalcularía contra el Silver ya modificado."""
    ids = q.select(F.trim("id_registro").alias(clave)).filter(F.col(clave) != "").distinct()
    return [r[0] for r in ids.join(ok.select(clave), clave, "left_anti").collect()]


def retirar(tabla, clave, ids):
    """Borra de Silver los registros que hoy son inválidos (ya quedaron en cuarentena)."""
    if not ids:
        return 0
    spark.createDataFrame([(i,) for i in ids], f"{clave} string").createOrReplaceTempView("ids_retiro")
    spark.sql(f"DELETE FROM {T(tabla)} WHERE {clave} IN (SELECT {clave} FROM ids_retiro)")
    return int(spark.sql(f"DESCRIBE HISTORY {T(tabla)} LIMIT 1")
               .select("operationMetrics").first()[0].get("numDeletedRows", 0))


ped_rechazados = rechazados(ped_q, ped_ok, "id_pedido")
ins, upd = merge_silver(ped_ok, "silver_pedidos", "id_pedido")
resumen["pedidos"] = dict(insertados=ins, actualizados=upd, cuarentena_nueva=merge_cuarentena(ped_q), bronze_nuevo=nuevo_b)
# Un pedido que ya estaba en Silver y hoy es inválido sale de Silver y deja de sumar venta.
dias_retirados = (spark.table(T("silver_pedidos")).filter(F.col("id_pedido").isin(ped_rechazados))
                  .select("fecha_pedido_dia").distinct().collect())
dias = sorted(set(dias) | {r[0] for r in dias_retirados})
resumen["pedidos"]["retirados"] = retirar("silver_pedidos", "id_pedido", ped_rechazados)

# ---- pagos: incremental por watermark de fecha_carga con ventana de reproceso
pag_raw, nuevo_b = aterrizar("pagos", run_id)
wm = spark.table(T("etl_watermark")).filter(F.col("tabla") == "pagos").select("ultimo_valor").first()
carga = F.expr("try_to_timestamp(fecha_carga, 'yyyy-MM-dd')")
if wm:
    # Los pagos que esperan a su pedido se releen siempre, aunque estén fuera de la ventana.
    pendientes = [r[0] for r in (
        spark.table(T("cuarentena"))
        .filter((F.col("tabla_origen") == "pagos") & F.col("regla_violada").isin("PAGO_HUERFANO", "PEDIDO_EN_CUARENTENA"))
        .select(F.trim("id_registro").alias("id_pago"))
        .join(spark.table(T("silver_pagos")), "id_pago", "left_anti")
        .union(spark.table(T("silver_pagos")).join(spark.table(T("silver_pedidos")), "id_pedido", "left_anti")
               .select("id_pago"))
        .distinct().collect())]
    pag_raw = pag_raw.filter(carga.isNull() | (carga >= F.expr(f"date_sub(DATE'{wm[0]}', {LOOKBACK_DIAS})"))
                             | F.trim("id_pago").isin(pendientes))
pag_raw = pag_raw.cache()
pedidos_dia = spark.table(T("silver_pedidos")).select("id_pedido", "fecha_pedido_dia")
ped_en_q = spark.table(T("cuarentena")).filter(F.col("tabla_origen") == "pedidos").select("id_registro").distinct()
negocio_pag = (spark.table(T("silver_pagos")).filter(F.col("hash_negocio").isNotNull())
               .groupBy("hash_negocio").agg(F.min("id_pago").alias("id_pago")))
pag_ok, pag_q = validar_pagos(pag_raw, pedidos_dia, ped_en_q, negocio_pag)
pag_ok = pag_ok.cache()
pag_rechazados = rechazados(pag_q, pag_ok, "id_pago")
ins, upd = merge_silver(pag_ok, "silver_pagos", "id_pago")
resumen["pagos"] = dict(insertados=ins, actualizados=upd, cuarentena_nueva=merge_cuarentena(pag_q), bronze_nuevo=nuevo_b)
resumen["pagos"]["retirados"] = retirar("silver_pagos", "id_pago", pag_rechazados)

maximo = pag_raw.select(F.max(carga).cast("date")).first()[0]
if maximo:
    nuevo_wm = max(maximo, wm[0]) if wm else maximo
    spark.sql(f"""
        MERGE INTO {T("etl_watermark")} t
        USING (SELECT 'pagos' AS tabla, DATE'{nuevo_wm}' AS ultimo_valor, '{run_id}' AS ultimo_run_id,
                      current_timestamp() AS actualizado_en) s
        ON t.tabla = s.tabla
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""")
'''

SOPORTE = '''# === 8. Soporte: opcional, y nunca altera el cálculo de venta ===
# Las fechas incoherentes se conservan marcadas y sin horas de resolución: inventar un
# SLA que la fuente no respalda sería peor que no tenerlo.
if contratos.get("tickets_soporte"):
    tic_raw, nuevo_b = aterrizar("tickets_soporte", run_id)
    tic_ok, tic_q = validar_tickets(tic_raw)
    tic_rechazados = rechazados(tic_q, tic_ok, "id_ticket")
    ins, upd = merge_silver(tic_ok, "silver_tickets", "id_ticket")
    resumen["tickets_soporte"] = dict(insertados=ins, actualizados=upd,
                                      cuarentena_nueva=merge_cuarentena(tic_q), bronze_nuevo=nuevo_b)
    resumen["tickets_soporte"]["retirados"] = retirar("silver_tickets", "id_ticket", tic_rechazados)


# ---- incidencias de calidad: se abren y se resuelven, nunca se borra el historial
def actualizar_incidencias(tabla, raw, q, col_id):
    """Solo se resuelven los ids efectivamente reevaluados en esta corrida. Que una fila
    no venga en el lote no prueba que su problema se haya corregido."""
    raw.select(F.trim(F.col(col_id)).alias("id_registro")).createOrReplaceTempView("ids_revisados")
    q.select("id_registro", "regla_violada").createOrReplaceTempView("q_nueva")
    for sentencia_sql in delta_sentencias_incidencias(T, tabla, run_id):
        spark.sql(sentencia_sql)


for _tabla, _raw, _q, _col in [("clientes", cli_raw, cli_q, "id_cliente"),
                               ("pedidos", ped_raw, ped_q, "id_pedido"),
                               ("pagos", pag_raw, pag_q, "id_pago")]:
    actualizar_incidencias(_tabla, _raw, _q, _col)
if contratos.get("tickets_soporte"):
    actualizar_incidencias("tickets_soporte", tic_raw, tic_q, "id_ticket")
'''

ESTRELLA = '''# === 10. Modelo estrella: dimensiones estables y hechos marcados con el run ===
# Las claves ya emitidas no se mueven entre cargas: si se renumeraran, cualquier informe
# guardado contra ellas quedaría apuntando a otra cosa.
from datetime import date as _date

_rango = spark.sql(f"""
    SELECT least(coalesce(min(f), DATE'{FECHA_MIN}'), DATE'{FECHA_MIN}'),
           greatest(coalesce(max(f), DATE'{FECHA_MAX}'), DATE'{FECHA_MAX}')
    FROM (SELECT fecha_pedido_dia AS f FROM {T('silver_pedidos')}
          UNION SELECT fecha_pago FROM {T('silver_pagos')}
          UNION SELECT cast(fecha_creacion AS DATE) FROM {T('silver_tickets')})""").first()

for paso in pasos_dimensiones(T, _rango[0], _rango[1]):
    spark.sql(sentencia(paso, T))
spark.sql(delta_refrescar_atributos_cliente(T))      # atributos al día, misma clave
for paso in pasos_hechos(T, run_id):
    spark.sql(sentencia(paso, T))
resumen["estrella"] = comprobar_estrella(spark, T)
print("estrella:", resumen["estrella"])
'''

PUBLICACION = '''# === 11. Publicación consistente sin transacción entre tablas ===
# DuckDB envuelve toda la corrida en una transacción; Delta solo garantiza atomicidad por
# tabla. Aquí la consistencia se consigue al revés: los hechos ya están escritos con su
# run_id, pero el consumidor lee las vistas v_fact_*, que filtran por el run publicado.
# Mientras el puntero no se mueva, Power BI y el reporte siguen viendo la carga anterior
# completa, nunca una a medias.
POLITICA = PoliticaPublicacion()      # sin umbrales inventados; configurar tras acordar U08

for sentencia_sql in sentencias_vistas_publicadas(T):
    spark.sql(sentencia_sql)

try:
    resumen["publicacion"] = validar_publicacion(spark, T, resumen, POLITICA)
except PublicacionBloqueada as e:
    # La carga queda escrita pero NO publicada: el puntero sigue en el run anterior.
    print("PUBLICACIÓN BLOQUEADA:", e)
    raise
spark.sql(delta_publicar(T, run_id, resumen["publicacion"]["venta_neta"]))
print("publicado:", resumen["publicacion"])
'''

GOLD = '''# === 9. Venta neta diaria: se recalcula solo para los días tocados (depende solo de Silver) ===
if RECALCULAR_GOLD:
    dias = sorted({r[0] for r in spark.table(T("silver_pedidos")).select("fecha_pedido_dia")
                   .union(spark.table(T("gold_venta_neta_diaria")).select("fecha")).distinct().collect()})
if dias:
    lista = ", ".join(f"DATE'{d}'" for d in dias)
    spark.sql(f"DELETE FROM {T('gold_venta_neta_diaria')} WHERE fecha IN ({lista})")
    spark.sql(f"""
        INSERT INTO {T('gold_venta_neta_diaria')}
        SELECT fecha_pedido_dia, canal, categoria, count(*), sum(valor_bruto), sum(descuento), sum(valor_neto)
        FROM {T('silver_pedidos')}
        WHERE estado = '{ESTADO_VENTA}' AND fecha_pedido_dia IN ({lista})
        GROUP BY fecha_pedido_dia, canal, categoria""")
resumen["dias_recalculados"] = len(dias)

for tabla in ("clientes", "pedidos", "pagos"):
    r = resumen[tabla]
    print(f"{tabla:9} insertados={r['insertados']:>6} actualizados={r['actualizados']:>4} "
          f"cuarentena_nueva={r['cuarentena_nueva']:>4} bronze={'nuevo' if r['bronze_nuevo'] else 'ya existia'}")
print("dias de venta recalculados:", resumen["dias_recalculados"])
'''

VERIFICACION = '''# === 12. Verificación contra el ETL local (solo aplica con el conjunto de datos completo del caso) ===
ESPERADO = {"pedidos_validos": 19270, "pagos_validos": 20124, "clientes_validos": 6040,
            "filas_gold": 7925, "venta_neta": 14_177_333_600}
real = {
    "pedidos_validos": spark.table(T("silver_pedidos")).count(),
    "pagos_validos": spark.table(T("silver_pagos")).count(),
    "clientes_validos": spark.table(T("silver_clientes")).count(),
    "filas_gold": spark.table(T("gold_venta_neta_diaria")).count(),
    "venta_neta": spark.table(T("gold_venta_neta_diaria")).agg(F.sum("venta_neta")).first()[0],
}
for k, v in ESPERADO.items():
    print(f"{k:18} esperado={v:>16,} real={real[k]:>16,} {'OK' if real[k] == v else 'DIFERENTE'}")
assert real == ESPERADO, "Las cifras no coinciden con el ETL local"

display(spark.table(T("cuarentena")).groupBy("tabla_origen", "regla_violada")
        .agg(F.countDistinct("id_registro").alias("registros")).orderBy("tabla_origen", F.desc("registros")))
'''


def celda(tipo, texto):
    base = {"id": hashlib.sha256((tipo + texto).encode()).hexdigest()[:8], "cell_type": tipo, "metadata": {}, "source": texto.splitlines(keepends=True)}
    if tipo == "code":
        base.update({"outputs": [], "execution_count": None})
    return base


cuerpo_reglas = "# === 2. Reglas de calidad (espejo de la versión pandas; ver spark/rules_spark.py) ===\n" + REGLAS
cuerpo_extensiones = ("# === 3. Extensiones: soporte, estrella, contratos, incidencias y publicación\n"
                      "# (espejo de andina_etl/{tickets,star,contracts,operations}.py; "
                      "ver spark/extensiones_spark.py) ===\n"
                      "from pyspark.sql.utils import AnalysisException\n" + EXTENSIONES)
nb = {
    "cells": [celda("markdown", INTRO), celda("code", CONFIG), celda("code", cuerpo_reglas),
              celda("code", cuerpo_extensiones), celda("code", DDL), celda("code", CONTRATOS_CELDA),
              celda("code", BRONZE_CELDA), celda("code", PIPELINE), celda("code", SOPORTE),
              celda("code", GOLD), celda("code", ESTRELLA), celda("code", PUBLICACION),
              celda("code", VERIFICACION)],
    "metadata": {
        "kernelspec": {"display_name": "PySpark", "language": "python", "name": "synapse_pyspark"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
destino = RAIZ / "fabric" / "notebooks" / "andina_etl_spark.ipynb"
destino.parent.mkdir(exist_ok=True)
destino.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("escrito", destino)
