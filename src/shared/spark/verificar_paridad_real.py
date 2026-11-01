"""Compara las reglas PySpark con el resultado del ETL local sobre los datos reales.

Uso (después de `python -m andina_etl`):
    python src/shared/spark/verificar_paridad_real.py [data/bronze] [data/warehouse.duckdb]

Lee la capa Bronze en Parquet con Spark, aplica las reglas de spark/rules_spark.py y
compara conteos por regla y totales contra las tablas del almacén DuckDB.
"""
import sys
from pathlib import Path

import duckdb
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules_spark as rs  # noqa: E402

bronze = Path(sys.argv[1] if len(sys.argv) > 1 else "data/bronze")
db = sys.argv[2] if len(sys.argv) > 2 else "data/warehouse.duckdb"

spark = (SparkSession.builder.master("local[2]").appName("paridad-real")
         .config("spark.sql.shuffle.partitions", "4").config("spark.ui.enabled", "false")
         .config("spark.sql.ansi.enabled", "true").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")


def leer(tabla):
    ruta = next(bronze.glob(f"{tabla}/ingest_date=*/{tabla}_*.parquet"))
    df = spark.read.parquet(ruta.as_posix())
    return df.select(*[c for c in df.columns if not c.startswith("_")])


cli_ok, cli_q = rs.validar_clientes(leer("clientes"))
ped_ok, ped_q = rs.validar_pedidos(
    leer("pedidos"), "2025-01-01", "2026-09-30", cli_ok.select("id_cliente"),
    spark.createDataFrame([], "hash_negocio string, id_pedido string"))
ped_ok = ped_ok.cache()
pag_ok, pag_q = rs.validar_pagos(
    leer("pagos"), ped_ok.select("id_pedido", "fecha_pedido_dia"),
    ped_q.select("id_registro").distinct(),
    spark.createDataFrame([], "hash_negocio string, id_pago string"))

spark_q = {(r["tabla_origen"], r["regla_violada"]): r["n"] for r in
           ped_q.unionByName(pag_q).unionByName(cli_q).groupBy("tabla_origen", "regla_violada")
           .agg(F.countDistinct("id_registro").alias("n")).collect()}
gold = (ped_ok.filter(F.col("estado") == "ENTREGADO")
        .groupBy("fecha_pedido_dia", "canal", "categoria")
        .agg(F.count("*").alias("n"), F.sum("valor_neto").alias("neto")))
spark_tot = {
    "pedidos_validos": ped_ok.count(),
    "pagos_validos": pag_ok.count(),
    "clientes_validos": cli_ok.count(),
    "filas_gold": gold.count(),
    "venta_neta": gold.agg(F.sum("neto")).first()[0],
}

con = duckdb.connect(db, read_only=True)
duck_q = {(t, r): n for t, r, n in con.execute(
    "SELECT tabla_origen, regla_violada, count(DISTINCT id_registro) FROM cuarentena GROUP BY 1,2").fetchall()}
duck_tot = {
    "pedidos_validos": con.execute("SELECT count(*) FROM silver_pedidos").fetchall()[0][0],
    "pagos_validos": con.execute("SELECT count(*) FROM silver_pagos").fetchall()[0][0],
    "clientes_validos": con.execute("SELECT count(*) FROM silver_clientes").fetchall()[0][0],
    "filas_gold": con.execute("SELECT count(*) FROM gold_venta_neta_diaria").fetchall()[0][0],
    "venta_neta": int(con.execute("SELECT sum(venta_neta) FROM gold_venta_neta_diaria").fetchall()[0][0]),
}

ok = True
print(f"{'indicador':28} {'spark':>16} {'duckdb':>16}")
for k in duck_tot:
    igual = spark_tot[k] == duck_tot[k]
    ok &= igual
    print(f"{k:28} {spark_tot[k]:>16,} {duck_tot[k]:>16,} {'OK' if igual else 'DIFERENTE'}")
print()
for k in sorted(set(spark_q) | set(duck_q)):
    a, b = spark_q.get(k, 0), duck_q.get(k, 0)
    ok &= a == b
    print(f"{k[0]:9} {k[1]:28} {a:>6} {b:>6} {'OK' if a == b else 'DIFERENTE'}")
print("\nPARIDAD COMPLETA" if ok else "\nHAY DIFERENCIAS")
spark.stop()
raise SystemExit(0 if ok else 1)
