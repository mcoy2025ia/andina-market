"""Pruebas del reporte corregido. Usan SQLite en memoria (con un esquema 'gold' adjunto): el mismo
SQL con parámetros '?' que se ejecuta en SQL Server con pyodbc."""
import sqlite3
from datetime import date, datetime

import pytest

import reporte_ventas as rv


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("ATTACH DATABASE ':memory:' AS gold")
    c.execute("CREATE TABLE gold.dim_canal (canal_key INTEGER, canal TEXT)")
    c.execute("""CREATE TABLE gold.fact_venta_neta_diaria (fecha_key INTEGER, canal_key INTEGER,
                 categoria_key INTEGER, num_pedidos INTEGER, venta_bruta INTEGER, descuento INTEGER,
                 venta_neta INTEGER)""")
    c.executemany("INSERT INTO gold.dim_canal VALUES (?,?)", [(1, "WEB"), (2, "APP"), (3, "TIENDA")])
    filas = [
        (20260910, 1, 1, 1, 1000, 100, 900),     # WEB, Moda
        (20260910, 1, 2, 1, 2000, 0, 2000),      # WEB, Hogar: se suman las categorías del día
        (20260910, 2, 1, 1, 3000, 300, 2700),    # APP
        (20260911, 1, 1, 1, 9999, 0, 9999),      # otro día
        (20260909, 1, 1, 1, 9999, 0, 9999),      # otro día
    ]
    c.executemany("INSERT INTO gold.fact_venta_neta_diaria VALUES (?,?,?,?,?,?,?)", filas)
    return c


def test_suma_las_categorias_del_dia_por_canal(conn):
    r = rv.ventas_por_canal(conn, date(2026, 9, 10))
    assert (r["WEB"].total, r["WEB"].pedidos) == (2900, 2)   # 900 + 2000
    assert (r["APP"].total, r["APP"].pedidos) == (2700, 1)


def test_canal_sin_ventas_no_divide_por_cero(conn):
    r = rv.ventas_por_canal(conn, date(2026, 9, 10))
    assert r["TIENDA"].total == 0 and r["TIENDA"].pedidos == 0
    assert r["TIENDA"].ticket is None


def test_dia_sin_pedidos_no_falla(conn):
    r = rv.ventas_por_canal(conn, date(2030, 1, 1))
    assert all(v.pedidos == 0 and v.ticket is None for v in r.values())


def test_llamadas_repetidas_dan_el_mismo_resultado(conn):
    # El defecto original (lista mutable por defecto) acumulaba pedidos entre llamadas.
    a = rv.ventas_por_canal(conn, date(2026, 9, 10))
    b = rv.ventas_por_canal(conn, date(2026, 9, 10))
    assert a == b
    assert a["WEB"].ticket == 1450  # 2900 / 2


def test_dia_a_reportar_es_ayer_en_hora_de_colombia():
    ahora = datetime(2026, 9, 11, 7, 0, tzinfo=rv.ZONA)
    assert rv.dia_a_reportar(ahora) == date(2026, 9, 10)
