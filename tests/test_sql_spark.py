"""Spark SQL (Fabric/Databricks) == DuckDB sobre los datos reales del almacén local.
Se omite sin PySpark, sin Java o sin data/warehouse.duckdb (corre antes scripts/cargar_datos.py),
y en Windows sin HADOOP_HOME (ver conftest.motivo_para_omitir_spark)."""
import re
from pathlib import Path

import pytest

from .conftest import motivo_para_omitir_spark

pyspark = pytest.importorskip("pyspark")
duckdb = pytest.importorskip("duckdb")
if motivo := motivo_para_omitir_spark(escribe_archivos=True):
    pytest.skip(motivo, allow_module_level=True)

RAIZ = Path(__file__).resolve().parents[1]
DB = RAIZ / "data" / "warehouse.duckdb"
if not DB.exists():
    pytest.skip("falta data/warehouse.duckdb", allow_module_level=True)


def _consultas(texto):
    texto = re.sub(r"--.*", "", texto)
    return [p.strip() for p in texto.split(";") if p.strip()]


def test_spark_sql_igual_a_duckdb(tmp_path):
    from pyspark.sql import SparkSession
    con = duckdb.connect(str(DB), read_only=True)
    spark = (SparkSession.builder.master("local[2]").appName("sql-paridad")
             .config("spark.sql.shuffle.partitions", "2").config("spark.ui.enabled", "false")
             .config("spark.sql.warehouse.dir", str(tmp_path / "wh")).getOrCreate())
    try:
        spark.sql("CREATE DATABASE IF NOT EXISTS silver")
        for t in ("clientes", "pedidos"):
            ruta = tmp_path / f"{t}.parquet"
            con.execute(f"COPY (SELECT * EXCLUDE (ingested_at) FROM silver_{t}) TO '{ruta.as_posix()}' (FORMAT parquet)")
            spark.read.parquet(ruta.as_posix()).write.mode("overwrite").saveAsTable(f"silver.{t}")
        sql_spark = _consultas((RAIZ / "fabric" / "sql" / "01_ventas_recompra.sql").read_text(encoding="utf-8"))
        sql_duck = [p for p in re.split(r";\s*\n", (RAIZ / "duckdb" / "01_ventas_recompra.sql").read_text(encoding="utf-8")) if "SELECT" in p]
        spark.sql(sql_spark[0])  # vista cliente maestro
        for s, d in zip(sql_spark[1:], sql_duck):
            a = [tuple(r) for r in spark.sql(s).collect()]
            b = [tuple(r) for r in con.execute(d).fetchall()]
            assert len(a) == len(b)
            for fa, fb in zip(a, b):
                for x, y in zip(fa, fb):
                    if isinstance(y, float) or isinstance(x, float):
                        assert (x is None and y is None) or abs(float(x) - float(y)) < 0.01
                    else:
                        assert str(x) == str(y)
    finally:
        spark.stop()
