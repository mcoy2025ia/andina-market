"""Pruebas del proceso completo: idempotencia, incremental y recálculo de la venta neta."""
import duckdb
import pytest

from andina_etl import store
from andina_etl.pipeline import ejecutar

from .conftest import datos_base, escribir_csvs

# Columnas que cambian entre ejecuciones por diseño (marcas de tiempo e identificadores de corrida).
VOLATILES = {"ingested_at", "run_id", "fecha_proceso", "actualizado_en", "ultimo_run_id"}
TABLAS = ["silver_clientes", "silver_pedidos", "silver_pagos", "cuarentena",
          "etl_watermark", "gold_venta_neta_diaria"]


@pytest.fixture
def entorno(tmp_path):
    raw = tmp_path / "raw"
    escribir_csvs(raw, datos_base())
    return raw, tmp_path / "wh.duckdb"


def _foto(db):
    """Contenido de todas las tablas, sin las columnas que varían por diseño."""
    con = duckdb.connect(str(db), read_only=True)
    foto = {}
    for t in TABLAS:
        cols = [c[0] for c in con.execute(f"DESCRIBE {t}").fetchall() if c[0] not in VOLATILES]
        foto[t] = con.execute(f"SELECT {', '.join(cols)} FROM {t} ORDER BY ALL").fetchall()
    con.close()
    return foto


def _q(db, sql):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_primera_carga_separa_validos_y_cuarentena(entorno):
    raw, db = entorno
    r = ejecutar(raw, db)
    assert r["pedidos"]["insertados"] == 5 and r["pagos"]["insertados"] == 3
    assert _q(db, "SELECT count(DISTINCT id_registro) FROM cuarentena WHERE tabla_origen='pedidos'") == [(5,)]
    assert _q(db, "SELECT count(DISTINCT id_registro) FROM cuarentena WHERE tabla_origen='pagos'") == [(6,)]
    # P005 rompe dos reglas: aparece dos veces en cuarentena pero es un solo registro
    assert _q(db, "SELECT count(*) FROM cuarentena WHERE id_registro='P005'") == [(2,)]


def test_venta_neta_solo_cuenta_entregados_y_normaliza_canal(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    filas = _q(db, "SELECT CAST(fecha AS VARCHAR), canal, categoria, num_pedidos, venta_neta "
                   "FROM gold_venta_neta_diaria ORDER BY fecha")
    assert filas == [
        ("2025-01-10", "APP", "Moda", 1, 90000),      # 'app ' -> APP; P004 duplicado no suma
        ("2025-02-01", "WEB", "Moda", 1, 180000),     # 'PAGINA WEB' -> WEB
        ("2025-03-03", "WEB", "Moda", 1, 80000),      # cliente desconocido: la venta se conserva
    ]  # CANCELADO (P002) y DEVUELTO (P010) no cuentan


def test_cliente_maestro_une_el_mismo_documento(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    assert _q(db, "SELECT id_cliente, id_cliente_maestro FROM v_cliente_maestro ORDER BY id_cliente") == [
        ("CL0000001", "CL0000001"), ("CL0000002", "CL0000002"), ("CL0000003", "CL0000001")]


def test_idempotencia_dos_ejecuciones_dejan_el_mismo_resultado(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    antes = _foto(db)
    r2 = ejecutar(raw, db)
    assert _foto(db) == antes
    for t in ("clientes", "pedidos"):
        assert r2[t]["insertados"] == 0 and r2[t]["actualizados"] == 0
        assert r2[t]["cuarentena_nueva"] == 0
    assert r2["pagos"]["insertados"] == 0 and r2["pagos"]["cuarentena_nueva"] == 0
    assert r2["dias_recalculados"] == 0


def test_incremental_agrega_solo_lo_nuevo(entorno):
    raw, db = entorno
    r1 = ejecutar(raw, db)
    assert _q(db, "SELECT CAST(ultimo_valor AS VARCHAR) FROM etl_watermark WHERE tabla='pagos'") == [("2025-03-08",)]
    antes = _foto(db)

    datos = datos_base()
    datos["pedidos"].append(dict(id_pedido="P011", id_cliente="CL0000002", fecha_pedido="2025-04-01 10:00:00",
                                 canal="TIENDA", categoria="Hogar", valor_bruto="300000", descuento="0",
                                 estado="ENTREGADO", fecha_entrega="2025-04-02"))
    datos["pagos"].append(dict(id_pago="G011", id_pedido="P011", fecha_pago="2025-04-01", valor="300000",
                               medio_pago="PSE", fecha_carga="2025-04-02"))
    escribir_csvs(raw, datos)
    r2 = ejecutar(raw, db)

    assert r2["pedidos"]["insertados"] == 1 and r2["pedidos"]["sin_cambios"] == 5
    assert r2["pagos"]["insertados"] == 1
    assert r2["dias_recalculados"] == 1  # solo el 2025-04-01
    assert _q(db, "SELECT CAST(ultimo_valor AS VARCHAR) FROM etl_watermark WHERE tabla='pagos'") == [("2025-04-02",)]
    despues = _foto(db)
    # lo que ya estaba no se tocó
    assert set(antes["silver_pedidos"]) <= set(despues["silver_pedidos"])
    assert len(despues["silver_pedidos"]) == len(antes["silver_pedidos"]) + 1
    assert len(despues["gold_venta_neta_diaria"]) == len(antes["gold_venta_neta_diaria"]) + 1
    assert r1["pedidos"]["insertados"] == 5


def test_cambio_de_estado_corrige_la_venta_del_dia(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    datos = datos_base()
    for fila in datos["pedidos"]:
        if fila["id_pedido"] == "P001":
            fila["estado"] = "DEVUELTO"  # el pedido se devolvió después de la primera carga
    escribir_csvs(raw, datos)
    r2 = ejecutar(raw, db)
    assert r2["pedidos"]["actualizados"] == 1 and r2["pedidos"]["insertados"] == 0
    assert _q(db, "SELECT count(*) FROM gold_venta_neta_diaria WHERE fecha = DATE '2025-01-10'") == [(0,)]


def test_pedido_que_cambia_de_dia_recalcula_ambos_dias(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    datos = datos_base()
    for fila in datos["pedidos"]:
        if fila["id_pedido"] == "P003":
            fila["fecha_pedido"] = "2025-02-05 09:00:00"
            fila["fecha_entrega"] = "2025-02-06"
    escribir_csvs(raw, datos)
    ejecutar(raw, db)
    dias = [d for (d,) in _q(db, "SELECT CAST(fecha AS VARCHAR) FROM gold_venta_neta_diaria ORDER BY fecha")]
    assert "2025-02-01" not in dias and "2025-02-05" in dias


def test_carga_tardia_dentro_de_la_ventana_se_reprocesa(entorno):
    """Un pago que llega con fecha_carga anterior al watermark, pero dentro del lookback, se carga."""
    raw, db = entorno
    ejecutar(raw, db)
    datos = datos_base()
    datos["pagos"].append(dict(id_pago="G012", id_pedido="P003", fecha_pago="2025-03-07", valor="1000",
                               medio_pago="PSE", fecha_carga="2025-03-07"))  # watermark = 2025-03-08, lookback 3d
    escribir_csvs(raw, datos)
    r2 = ejecutar(raw, db)
    assert r2["pagos"]["insertados"] == 1


def test_caida_entre_silver_y_gold_no_deja_nada_a_medias(entorno, tmp_path, monkeypatch):
    raw, db = entorno
    limpio = tmp_path / "limpio.duckdb"
    ejecutar(raw, limpio, bronze_dir=tmp_path / "bronze_limpio")
    esperado = _foto(limpio)

    def caida(*a, **k):
        raise RuntimeError("caída simulada")
    monkeypatch.setattr(store, "refrescar_venta_neta", caida)
    with pytest.raises(RuntimeError):
        ejecutar(raw, db)
    assert _q(db, "SELECT count(*) FROM silver_pedidos") == [(0,)]  # se deshizo toda la corrida
    assert _q(db, "SELECT estado FROM etl_run_log") == [("FALLIDO",)]

    monkeypatch.undo()
    ejecutar(raw, db)  # volver a ejecutar basta
    assert _foto(db) == esperado


def test_pago_que_llega_antes_que_su_pedido_se_carga_cuando_llega_el_pedido(entorno):
    raw, db = entorno
    ejecutar(raw, db)  # G004 queda huérfano; su fecha_carga (2025-02-02) ya está fuera de la ventana
    datos = datos_base()
    datos["pedidos"].append(dict(id_pedido="PNOEXISTE", id_cliente="CL0000002", fecha_pedido="2025-02-01 08:00:00",
                                 canal="WEB", categoria="Hogar", valor_bruto="5000", descuento="0",
                                 estado="ENTREGADO", fecha_entrega="2025-02-02"))
    escribir_csvs(raw, datos)
    r2 = ejecutar(raw, db)
    assert r2["pagos"]["insertados"] == 1
    assert _q(db, "SELECT id_pedido FROM silver_pagos WHERE id_pago = 'G004'") == [("PNOEXISTE",)]


def test_pedido_cargado_que_pasa_a_invalido_sale_de_silver_y_de_la_venta(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    datos = datos_base()
    for fila in datos["pedidos"]:
        if fila["id_pedido"] == "P003":
            fila["descuento"] = "999999"  # la fuente corrige el pedido y ahora es inválido
    escribir_csvs(raw, datos)
    r2 = ejecutar(raw, db)
    assert r2["pedidos"]["retirados"] == 1
    assert _q(db, "SELECT count(*) FROM silver_pedidos WHERE id_pedido = 'P003'") == [(0,)]
    assert _q(db, "SELECT count(*) FROM gold_venta_neta_diaria WHERE fecha = DATE '2025-02-01'") == [(0,)]
    # su pago válido también sale de Silver y queda en cuarentena por pedido rechazado
    assert r2["pagos"]["retirados"] == 1
    assert _q(db, "SELECT regla_violada FROM cuarentena WHERE id_registro = 'G003'") == [("PEDIDO_EN_CUARENTENA",)]
    assert ejecutar(raw, db)["dias_recalculados"] == 0  # y sigue siendo idempotente


def test_carga_con_solo_pedidos_invalidos_no_falla(tmp_path):
    datos = datos_base()
    datos["pedidos"] = [f for f in datos["pedidos"] if f["id_pedido"] in {"P005", "P006", "P007", "P009"}]
    escribir_csvs(tmp_path / "raw", datos)
    db = tmp_path / "wh.duckdb"
    r = ejecutar(tmp_path / "raw", db)
    assert r["pedidos"]["insertados"] == 0 and r["pagos"]["insertados"] == 0
    assert _q(db, "SELECT count(DISTINCT id_registro) FROM cuarentena WHERE tabla_origen = 'pagos'") == [
        (len(datos["pagos"]),)]


def test_recalcular_gold_reconstruye_todos_los_dias(entorno):
    raw, db = entorno
    ejecutar(raw, db)
    esperado = _foto(db)
    con = duckdb.connect(str(db))
    con.execute("DELETE FROM gold_venta_neta_diaria")  # p. ej., tras cambiar la definición de venta
    con.close()
    assert ejecutar(raw, db)["dias_recalculados"] == 0  # sin datos nuevos no se recalcula nada
    r = ejecutar(raw, db, recalcular_gold=True)
    assert r["dias_recalculados"] == 4  # los 4 días con pedidos en Silver, de cualquier estado
    assert _foto(db) == esperado
