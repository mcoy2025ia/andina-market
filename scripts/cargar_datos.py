"""Carga los 4 CSV al almacén local (Bronze Parquet + DuckDB) y verifica el resultado.

Uso, desde la raíz del repositorio:
    python scripts/cargar_datos.py                 # carga incremental sobre data/warehouse.duckdb
    python scripts/cargar_datos.py --desde-cero    # borra almacén y Bronze y recarga todo
    python scripts/cargar_datos.py --recalcular-gold  # recalcula todos los días de venta neta

Los CSV deben estar en data/original/: clientes.csv, pedidos.csv, pagos.csv (tickets_soporte.csv es opcional).
"""
import argparse
import shutil
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "shared"))

from andina_etl.pipeline import ejecutar  # noqa: E402

REQUERIDOS = ["clientes.csv", "pedidos.csv", "pagos.csv"]
# Resultados de referencia con los datos entregados (para detectar una carga distinta).
ESPERADO = {"silver_clientes": 6040, "silver_pedidos": 19270, "silver_pagos": 20124,
            "gold_venta_neta_diaria": 7925}
VENTA_NETA_ESPERADA = 14_177_333_600


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", default=str(RAIZ / "data" / "original"))
    p.add_argument("--db", default=str(RAIZ / "data" / "warehouse.duckdb"))
    p.add_argument("--bronze", default=str(RAIZ / "data" / "bronze"))
    p.add_argument("--desde-cero", action="store_true", help="borra el almacén y Bronze antes de cargar")
    p.add_argument("--recalcular-gold", action="store_true",
                   help="recalcula todos los días de venta (tras cambiar la definición de venta o una regla)")
    a = p.parse_args()

    raw = Path(a.raw)
    faltan = [f for f in REQUERIDOS if not (raw / f).exists()]
    if faltan:
        sys.exit(f"Faltan archivos en {raw}: {', '.join(faltan)}\nCopia ahí los CSV de la prueba.")

    if a.desde_cero:
        for ruta in (Path(a.db), Path(a.db + ".wal")):
            ruta.unlink(missing_ok=True)
        shutil.rmtree(a.bronze, ignore_errors=True)
        print("Almacén y Bronze borrados.")

    resumen = ejecutar(str(raw), a.db, bronze_dir=a.bronze, recalcular_gold=a.recalcular_gold)
    print("Resumen de la carga:", resumen)

    con = duckdb.connect(a.db, read_only=True)
    print("\nVerificación")
    ok = True
    for tabla, esperado in ESPERADO.items():
        n = con.execute(f"SELECT count(*) FROM {tabla}").fetchall()[0][0]
        marca = "OK" if n == esperado else "DISTINTO (¿otros datos?)"
        ok &= n == esperado
        print(f"  {tabla:26} {n:>8,}  esperado {esperado:>8,}  {marca}")
    venta = int(con.execute("SELECT sum(venta_neta) FROM gold_venta_neta_diaria").fetchall()[0][0])
    marca = "OK" if venta == VENTA_NETA_ESPERADA else "DISTINTO (¿otros datos?)"
    ok &= venta == VENTA_NETA_ESPERADA
    print(f"  {'venta neta total':26} {venta:>16,}  esperado {VENTA_NETA_ESPERADA:>14,}  {marca}")
    print("\nCARGA CORRECTA" if ok else "\nLa carga terminó, pero los totales no coinciden con los de referencia.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
