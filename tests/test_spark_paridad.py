"""Paridad entre las reglas pandas (andina_etl) y las reglas PySpark (spark/rules_spark.py).

Se ejecuta con ANSI activado, que es el modo más estricto: si pasa así, no depende de que el
runtime sea permisivo con valores sucios. Se omite si no hay PySpark o Java (y en Windows
con Python 3.12, ver conftest.motivo_para_omitir_spark).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

from .conftest import COLS_CLIENTES, COLS_PAGOS, COLS_PEDIDOS, datos_base, motivo_para_omitir_spark

pyspark = pytest.importorskip("pyspark")
if motivo := motivo_para_omitir_spark():
    pytest.skip(motivo, allow_module_level=True)

from andina_etl import rules  # noqa: E402
from andina_etl.config import Config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "shared" / "spark"))
import rules_spark as rs  # noqa: E402

CFG = Config()


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[2]").appName("paridad")
         .config("spark.sql.shuffle.partitions", "2").config("spark.ui.enabled", "false")
         .config("spark.sql.ansi.enabled", "true").getOrCreate())
    yield s
    s.stop()


def _sdf(spark, filas, cols):
    return spark.createDataFrame(pd.DataFrame(filas, columns=cols, dtype=str).astype(object)
                                 .where(lambda d: d.notna(), None).values.tolist(), schema=", ".join(f"{c} string" for c in cols))


def _pdf(sdf):
    """DataFrame de Spark -> pandas vía collect(): evita toPandas(), que en PySpark 3.5 no es
    compatible con pandas 3."""
    return pd.DataFrame([tuple(r) for r in sdf.collect()], columns=sdf.columns)


def _pares(df):
    return sorted(map(tuple, df[["id_registro", "regla_violada"]].values.tolist()))


def test_pedidos_misma_cuarentena_y_mismos_validos(spark):
    datos = datos_base()
    raw_pd = pd.DataFrame(datos["pedidos"], columns=COLS_PEDIDOS, dtype=str)
    ok_pd, q_pd = rules.validar_pedidos(raw_pd, CFG, {"CL0000001", "CL0000002", "CL0000003"})

    clientes = spark.createDataFrame([("CL0000001",), ("CL0000002",), ("CL0000003",)], "id_cliente string")
    vacio = spark.createDataFrame([], "hash_negocio string, id_pedido string")
    ok_sp, q_sp = rs.validar_pedidos(_sdf(spark, datos["pedidos"], COLS_PEDIDOS), "2025-01-01", "2026-09-30",
                                     clientes, vacio)

    assert _pares(_pdf(q_sp)) == _pares(q_pd)
    assert sorted(_pdf(ok_sp)["id_pedido"]) == sorted(ok_pd["id_pedido"])
    # el hash de fila (sobre datos crudos) es idéntico en ambas implementaciones
    assert sorted(_pdf(ok_sp)["row_hash"]) == sorted(ok_pd["row_hash"])
    a = _pdf(ok_sp).set_index("id_pedido").sort_index()
    b = ok_pd.set_index("id_pedido").sort_index()
    assert (a["canal"] == b["canal"]).all() and (a["valor_neto"] == b["valor_neto"]).all()
    assert (a["flag_cliente_desconocido"] == b["flag_cliente_desconocido"]).all()


def test_pagos_misma_cuarentena_y_mismos_validos(spark):
    datos = datos_base()
    raw_pd = pd.DataFrame(datos["pagos"], columns=COLS_PAGOS, dtype=str)
    pedidos_dia = pd.Series(pd.to_datetime(["2025-01-10", "2025-02-01", "2025-03-03", "2025-03-04", "2025-01-10"]),
                            index=["P001", "P003", "P008", "P010", "P002"])
    ok_pd, q_pd = rules.validar_pagos(raw_pd, CFG, pedidos_dia, {"P004"})

    pd_sp = spark.createDataFrame([(i, d.date()) for i, d in pedidos_dia.items()], "id_pedido string, fecha_pedido_dia date")
    q_ids = spark.createDataFrame([("P004",)], "id_registro string")
    vacio = spark.createDataFrame([], "hash_negocio string, id_pago string")
    ok_sp, q_sp = rs.validar_pagos(_sdf(spark, datos["pagos"], COLS_PAGOS), pd_sp, q_ids, vacio)

    assert _pares(_pdf(q_sp)) == _pares(q_pd)
    assert sorted(_pdf(ok_sp)["id_pago"]) == sorted(ok_pd["id_pago"])
    reemb = _pdf(ok_sp).set_index("id_pago")["es_reembolso"]
    assert bool(reemb["G006"]) is True and bool(reemb["G001"]) is False


def test_ids_repetidos_misma_cuarentena(spark):
    datos = datos_base()
    pedidos = datos["pedidos"] + [dict(datos["pedidos"][0], valor_bruto="999000")]  # P001 dos veces
    pagos = datos["pagos"] + [dict(datos["pagos"][0], valor="1")]                  # G001 dos veces
    clientes = {"CL0000001", "CL0000002", "CL0000003"}
    _, q_ped_pd = rules.validar_pedidos(pd.DataFrame(pedidos, columns=COLS_PEDIDOS, dtype=str), CFG, clientes)
    _, q_ped_sp = rs.validar_pedidos(
        _sdf(spark, pedidos, COLS_PEDIDOS), "2025-01-01", "2026-09-30",
        spark.createDataFrame([(c,) for c in sorted(clientes)], "id_cliente string"),
        spark.createDataFrame([], "hash_negocio string, id_pedido string"))
    assert _pares(_pdf(q_ped_sp)) == _pares(q_ped_pd)

    pedidos_dia = pd.Series(pd.to_datetime(["2025-01-10", "2025-02-01", "2025-03-04"]), index=["P001", "P003", "P010"])
    _, q_pag_pd = rules.validar_pagos(pd.DataFrame(pagos, columns=COLS_PAGOS, dtype=str), CFG, pedidos_dia, set())
    _, q_pag_sp = rs.validar_pagos(
        _sdf(spark, pagos, COLS_PAGOS),
        spark.createDataFrame([(i, d.date()) for i, d in pedidos_dia.items()], "id_pedido string, fecha_pedido_dia date"),
        spark.createDataFrame([], "id_registro string"),
        spark.createDataFrame([], "hash_negocio string, id_pago string"))
    assert _pares(_pdf(q_pag_sp)) == _pares(q_pag_pd)


def test_clientes_documento_y_cohorte(spark):
    datos = datos_base()
    ok_sp, q_sp = rs.validar_clientes(_sdf(spark, datos["clientes"], COLS_CLIENTES))
    ok_pd, _ = rules.validar_clientes(pd.DataFrame(datos["clientes"], columns=COLS_CLIENTES, dtype=str))
    a = _pdf(ok_sp).set_index("id_cliente").sort_index()
    b = ok_pd.set_index("id_cliente").sort_index()
    assert q_sp.count() == 0
    assert (a["documento_limpio"] == b["documento_limpio"]).all()
    assert (pd.to_datetime(a["cohorte_registro"]) == pd.to_datetime(b["cohorte_registro"])).all()
    assert (a["row_hash"] == b["row_hash"]).all()


def test_pesos_exactos_y_fracciones_paridad(spark):
    valores = ['9007199254740993', '100.00', '100.5', 'NaN', 'Infinity', str(2**63), '-1']
    df = spark.createDataFrame([(i,v) for i,v in enumerate(valores)], 'i int, valor string')
    real = [r[0] for r in df.select('i', rs._pesos('valor').alias('n')).orderBy('i').select('n').collect()]
    esperado = [None if pd.isna(v) else int(v) for v in rules.parsear_pesos(pd.Series(valores))]
    assert real == esperado
