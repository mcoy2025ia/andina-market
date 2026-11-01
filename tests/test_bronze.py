"""Pruebas de la capa Bronze: cruda, inmutable e idempotente."""
import duckdb
import pytest

from andina_etl.pipeline import ejecutar

from .conftest import datos_base, escribir_csvs


@pytest.fixture
def entorno(tmp_path):
    raw = tmp_path / "raw"
    escribir_csvs(raw, datos_base())
    return raw, tmp_path / "wh.duckdb", tmp_path / "bronze"


def _manifiesto(db):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute("SELECT tabla, filas FROM bronze_manifest ORDER BY tabla").fetchall()
    finally:
        con.close()


def test_bronze_guarda_lo_crudo_como_texto_con_trazabilidad(entorno):
    raw, db, bronze = entorno
    ejecutar(raw, db, bronze_dir=bronze)
    archivos = list(bronze.glob("pedidos/ingest_date=*/pedidos_*.parquet"))
    assert len(archivos) == 1
    con = duckdb.connect()
    cols = {c[0]: c[1] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{archivos[0].as_posix()}')").fetchall()}
    assert all(cols[c] == "VARCHAR" for c in ("id_pedido", "fecha_pedido", "valor_bruto", "canal"))
    assert {"_ingested_at", "_run_id", "_source_file", "_source_sha256"} <= set(cols)
    # el canal sucio se conserva tal cual; la limpieza es trabajo de Silver, no de Bronze
    assert con.execute(f"SELECT count(*) FROM read_parquet('{archivos[0].as_posix()}') WHERE canal = 'app '").fetchall() == [(1,)]
    # los vacíos de la fuente quedan como NULL y no como texto
    assert con.execute(f"SELECT count(*) FROM read_parquet('{archivos[0].as_posix()}') WHERE fecha_entrega IS NULL").fetchall() == [(1,)]


def test_bronze_conserva_todas_las_filas_incluidas_las_invalidas(entorno):
    raw, db, bronze = entorno
    ejecutar(raw, db, bronze_dir=bronze)
    assert _manifiesto(db) == [("clientes", 3), ("pagos", 9), ("pedidos", 10)]


def test_mismo_archivo_dos_veces_no_escribe_otro_bronze(entorno):
    raw, db, bronze = entorno
    ejecutar(raw, db, bronze_dir=bronze)
    antes = sorted(p.name for p in bronze.rglob("*.parquet"))
    r2 = ejecutar(raw, db, bronze_dir=bronze)
    assert sorted(p.name for p in bronze.rglob("*.parquet")) == antes
    assert not any(i["nuevo"] for i in r2["bronze"].values())
    assert len(_manifiesto(db)) == 3


def test_archivo_distinto_crea_un_snapshot_nuevo_sin_tocar_el_anterior(entorno):
    raw, db, bronze = entorno
    ejecutar(raw, db, bronze_dir=bronze)
    primero = {p: p.stat().st_mtime_ns for p in bronze.rglob("pedidos_*.parquet")}
    datos = datos_base()
    datos["pedidos"].append(dict(id_pedido="P011", id_cliente="CL0000002", fecha_pedido="2025-04-01 10:00:00",
                                 canal="TIENDA", categoria="Hogar", valor_bruto="300000", descuento="0",
                                 estado="ENTREGADO", fecha_entrega="2025-04-02"))
    escribir_csvs(raw, datos)
    r2 = ejecutar(raw, db, bronze_dir=bronze)
    assert r2["bronze"]["pedidos"]["nuevo"] is True and r2["bronze"]["clientes"]["nuevo"] is False
    despues = list(bronze.rglob("pedidos_*.parquet"))
    assert len(despues) == 2
    assert all(p.stat().st_mtime_ns == t for p, t in primero.items())  # inmutable
