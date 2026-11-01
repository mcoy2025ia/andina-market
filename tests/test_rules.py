"""Pruebas unitarias de las reglas de calidad (sin base de datos)."""
import pandas as pd
import pytest

from andina_etl import rules
from andina_etl.config import Config

from .conftest import COLS_CLIENTES, COLS_PAGOS, COLS_PEDIDOS, df_crudo

CFG = Config()
CLIENTES = {"CL0000001", "CL0000002"}


@pytest.mark.parametrize("entrada, esperado", [
    ("APP", "APP"), ("app", "APP"), ("App", "APP"), ("APLICACION", "APP"), ("APLICACIÓN", "APP"),
    ("WEB", "WEB"), ("web ", "WEB"), ("Web", "WEB"), ("PAGINA WEB", "WEB"),
    ("TIENDA", "TIENDA"), ("Tienda", "TIENDA"), ("TIENDA FISICA", "TIENDA"),
    ("MARTE", None), ("", None), (None, None),
])
def test_normalizar_canal(entrada, esperado):
    assert rules.normalizar_canal(entrada) == esperado


@pytest.mark.parametrize("entrada, esperado", [
    ("294.814.976", "294814976"),
    (" 43541913 ", "43541913"),
    ("00789490401", "789490401"),
    ("1000174227", "1000174227"),
    (None, None),
])
def test_limpiar_documento(entrada, esperado):
    assert rules.limpiar_documento(entrada) == esperado


def test_fecha_pago_no_confunde_dia_con_mes():
    serie = pd.Series(["2026-04-03", "03/04/2026", "31/02/2026", "basura", None])
    r = rules.parsear_fecha_pago(serie)
    assert r[0] == pd.Timestamp("2026-04-03")
    assert r[1] == pd.Timestamp("2026-04-03")  # 3 de abril, no 4 de marzo
    assert r[2:].isna().all()


def _pedido(**cambios):
    base = dict(id_pedido="P1", id_cliente="CL0000001", fecha_pedido="2025-05-10 10:00:00", canal="WEB",
                categoria="Moda", valor_bruto="100000", descuento="10000", estado="ENTREGADO",
                fecha_entrega="2025-05-12")
    base.update(cambios)
    return base


@pytest.mark.parametrize("cambios, reglas_esperadas", [
    (dict(id_pedido=None), {"ID_PEDIDO_NULO"}),
    (dict(canal="MARTE"), {"CANAL_DESCONOCIDO"}),
    (dict(estado="PERDIDO"), {"ESTADO_INVALIDO"}),
    (dict(fecha_pedido="no es fecha"), {"FECHA_PEDIDO_INVALIDA"}),
    (dict(fecha_pedido="2027-12-22 10:00:00", fecha_entrega="2027-12-23"), {"FECHA_FUERA_DE_RANGO"}),
    (dict(fecha_pedido="2024-12-31 23:59:00", fecha_entrega="2025-01-02"), {"FECHA_FUERA_DE_RANGO"}),
    # el descuento (10.000) también queda mayor que el bruto: dos reglas, un registro
    (dict(valor_bruto="-5000"), {"VALOR_BRUTO_NO_POSITIVO", "DESCUENTO_INVALIDO"}),
    (dict(valor_bruto="0", descuento="0"), {"VALOR_BRUTO_NO_POSITIVO"}),
    (dict(descuento="150000"), {"DESCUENTO_INVALIDO"}),
    (dict(descuento="-1"), {"DESCUENTO_INVALIDO"}),
    (dict(fecha_entrega=None), {"ENTREGADO_SIN_FECHA"}),
    (dict(fecha_entrega="2025-05-09"), {"ENTREGA_ANTERIOR_A_PEDIDO"}),
])
def test_pedido_con_error_va_a_cuarentena(cambios, reglas_esperadas):
    ok, q = rules.validar_pedidos(df_crudo([_pedido(**cambios)], COLS_PEDIDOS), CFG, CLIENTES)
    assert ok.empty
    assert set(q["regla_violada"]) == reglas_esperadas  # exacto: también detecta reglas que disparan de más


def test_id_pedido_repetido_manda_todas_las_copias_a_cuarentena():
    filas = [_pedido(), _pedido(valor_bruto="999000", fecha_pedido="2025-05-11 10:00:00", fecha_entrega="2025-05-12")]
    ok, q = rules.validar_pedidos(df_crudo(filas, COLS_PEDIDOS), CFG, CLIENTES)
    assert ok.empty
    assert list(q["regla_violada"]) == ["ID_PEDIDO_DUPLICADO", "ID_PEDIDO_DUPLICADO"]


def test_pedido_valido_se_tipa_y_calcula_neto():
    ok, q = rules.validar_pedidos(df_crudo([_pedido(canal="pagina web ")], COLS_PEDIDOS), CFG, CLIENTES)
    assert q.empty
    fila = ok.iloc[0]
    assert fila["canal"] == "WEB"
    assert fila["valor_neto"] == 90000
    assert fila["fecha_pedido_dia"] == pd.Timestamp("2025-05-10")


def test_cliente_inexistente_no_se_descarta_se_marca():
    ok, q = rules.validar_pedidos(df_crudo([_pedido(id_cliente="CLXXXXXXX")], COLS_PEDIDOS), CFG, CLIENTES)
    assert q.empty
    assert bool(ok.iloc[0]["flag_cliente_desconocido"]) is True


def test_duplicado_logico_gana_el_menor_id_aunque_cambie_canal():
    filas = [_pedido(id_pedido="P9", canal="app"), _pedido(id_pedido="P2", canal="APP")]
    ok, q = rules.validar_pedidos(df_crudo(filas, COLS_PEDIDOS), CFG, CLIENTES)
    assert list(ok["id_pedido"]) == ["P2"]
    assert list(q["id_registro"]) == ["P9"] and list(q["regla_violada"]) == ["DUPLICADO_LOGICO"]


def test_duplicado_gana_el_que_ya_esta_en_silver():
    ya_cargado = rules.hash_filas(df_crudo([_pedido()], COLS_PEDIDOS), ["id_cliente", "fecha_pedido", "valor_bruto", "categoria"])[0]
    existente = {ya_cargado: "P9"}
    ok, q = rules.validar_pedidos(df_crudo([_pedido(id_pedido="P2")], COLS_PEDIDOS), CFG, CLIENTES, existente)
    assert ok.empty and list(q["regla_violada"]) == ["DUPLICADO_LOGICO"]


def test_hash_es_determinista_y_sensible_al_contenido():
    a = df_crudo([_pedido()], COLS_PEDIDOS)
    b = df_crudo([_pedido(descuento="20000")], COLS_PEDIDOS)
    assert rules.hash_filas(a, COLS_PEDIDOS)[0] == rules.hash_filas(a.copy(), COLS_PEDIDOS)[0]
    assert rules.hash_filas(a, COLS_PEDIDOS)[0] != rules.hash_filas(b, COLS_PEDIDOS)[0]


def _pago(**cambios):
    base = dict(id_pago="G1", id_pedido="P1", fecha_pago="2025-05-10", valor="90000",
                medio_pago="PSE", fecha_carga="2025-05-11")
    base.update(cambios)
    return base


PEDIDOS_DIA = pd.Series(pd.to_datetime(["2025-05-10"]), index=["P1"])


@pytest.mark.parametrize("cambios, regla", [
    (dict(id_pago=None), "ID_PAGO_NULO"),
    (dict(id_pedido=None), "ID_PEDIDO_NULO"),
    (dict(id_pedido="PX"), "PAGO_HUERFANO"),
    (dict(valor="0"), "VALOR_INVALIDO"),
    (dict(medio_pago="Trueque"), "MEDIO_PAGO_INVALIDO"),
    (dict(fecha_pago="31/02/2025"), "FECHA_PAGO_INVALIDA"),
    (dict(fecha_carga="ayer"), "FECHA_CARGA_INVALIDA"),
    (dict(fecha_pago="2025-05-09"), "PAGO_ANTERIOR_A_PEDIDO"),
])
def test_pago_con_error_va_a_cuarentena(cambios, regla):
    ok, q = rules.validar_pagos(df_crudo([_pago(**cambios)], COLS_PAGOS), CFG, PEDIDOS_DIA, set())
    assert ok.empty
    assert set(q["regla_violada"]) == {regla}


def test_pagos_sin_ningun_pedido_en_silver_no_fallan():
    """Primera carga en la que ningún pedido fue válido: Silver de pedidos está vacío."""
    vacio = pd.Series([], dtype="datetime64[ns]", index=pd.Index([], dtype=object))
    ok, q = rules.validar_pagos(df_crudo([_pago()], COLS_PAGOS), CFG, vacio, set())
    assert ok.empty and list(q["regla_violada"]) == ["PAGO_HUERFANO"]


def test_id_pago_repetido_manda_todas_las_copias_a_cuarentena():
    filas = [_pago(), _pago(valor="1000")]
    ok, q = rules.validar_pagos(df_crudo(filas, COLS_PAGOS), CFG, PEDIDOS_DIA, set())
    assert ok.empty and list(q["regla_violada"]) == ["ID_PAGO_DUPLICADO", "ID_PAGO_DUPLICADO"]


def test_pago_de_pedido_en_cuarentena_se_distingue_del_huerfano():
    ok, q = rules.validar_pagos(df_crudo([_pago(id_pedido="PQ")], COLS_PAGOS), CFG, PEDIDOS_DIA, {"PQ"})
    assert list(q["regla_violada"]) == ["PEDIDO_EN_CUARENTENA"]


def test_reembolso_se_marca_y_pasa():
    ok, q = rules.validar_pagos(df_crudo([_pago(valor="-90000")], COLS_PAGOS), CFG, PEDIDOS_DIA, set())
    assert q.empty and bool(ok.iloc[0]["es_reembolso"]) is True


def test_pago_duplicado_se_detecta_aunque_la_fecha_venga_en_otro_formato():
    filas = [_pago(id_pago="G1", fecha_pago="2025-05-10"), _pago(id_pago="G2", fecha_pago="10/05/2025")]
    ok, q = rules.validar_pagos(df_crudo(filas, COLS_PAGOS), CFG, PEDIDOS_DIA, set())
    assert list(ok["id_pago"]) == ["G1"]
    assert list(q["id_registro"]) == ["G2"]


def test_cliente_con_id_duplicado_va_a_cuarentena():
    filas = [
        dict(id_cliente="C1", nombre="A", documento="1", ciudad="Cali", canal_registro="APP", fecha_registro="2025-01-01"),
        dict(id_cliente="C1", nombre="B", documento="2", ciudad="Cali", canal_registro="APP", fecha_registro="2025-01-02"),
    ]
    ok, q = rules.validar_clientes(df_crudo(filas, COLS_CLIENTES))
    assert len(ok) == 1 and list(q["regla_violada"]) == ["ID_CLIENTE_DUPLICADO"]


@pytest.mark.parametrize("cambios, regla", [
    (dict(id_cliente=None), "ID_CLIENTE_NULO"),
    (dict(fecha_registro="31/02/2025"), "FECHA_REGISTRO_INVALIDA"),
])
def test_cliente_con_error_va_a_cuarentena(cambios, regla):
    fila = dict(id_cliente="C1", nombre="A", documento="1", ciudad="Cali", canal_registro="APP",
                fecha_registro="2025-01-01")
    fila.update(cambios)
    ok, q = rules.validar_clientes(df_crudo([fila], COLS_CLIENTES))
    assert ok.empty and set(q["regla_violada"]) == {regla}
