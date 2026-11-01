"""Uso: python -m andina_etl --raw data/original --db data/warehouse.duckdb"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import duckdb

from .config import Config
from .pipeline import ejecutar
from .operations import PoliticaPublicacion


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="andina_etl", description="Carga pedidos y pagos de Andina Market.")
    p.add_argument("--raw", default="data/original", help="carpeta con los CSV de origen")
    p.add_argument("--db", default="data/warehouse.duckdb", help="archivo DuckDB de destino")
    p.add_argument("--bronze", default=None, help="carpeta de la capa Bronze en Parquet (por defecto, junto a la base)")
    p.add_argument("--fecha-min", default="2025-01-01", help="fecha_pedido mínima válida (AAAA-MM-DD)")
    p.add_argument("--fecha-max", default="2026-09-30", help="fecha_pedido máxima válida (AAAA-MM-DD)")
    p.add_argument("--lookback-dias", type=int, default=3, help="ventana de reproceso de pagos")
    p.add_argument("--recalcular-gold", action="store_true",
                   help="recalcula todos los días de venta (tras cambiar la definición de venta)")
    p.add_argument("--reconciliar", action="store_true", help="relee todos los pagos; no aplica bajas por ausencia")
    p.add_argument("--politica", type=Path, help="JSON con umbrales aprobados de publicación")
    a = p.parse_args(argv)

    cfg = Config(date.fromisoformat(a.fecha_min), date.fromisoformat(a.fecha_max), a.lookback_dias)
    Path(a.db).parent.mkdir(parents=True, exist_ok=True)
    opciones = json.loads(a.politica.read_text(encoding="utf-8")) if a.politica else {}
    if opciones.get("fecha_minima_datos"):
        opciones["fecha_minima_datos"] = date.fromisoformat(opciones["fecha_minima_datos"])
    r = ejecutar(a.raw, a.db, cfg, a.bronze, recalcular_gold=a.recalcular_gold,
                 reconciliar=a.reconciliar, politica=PoliticaPublicacion(**opciones))

    print(f"\nRun {r['run_id']}")
    print(f"{'tabla':10} {'leídos':>8} {'insertados':>11} {'actualiz.':>10} {'sin cambio':>11} {'cuarent. nueva':>15}")
    for t in ("clientes", "pedidos", "pagos"):
        x = r[t]
        print(f"{t:10} {x['leidos']:>8} {x['insertados']:>11} {x['actualizados']:>10} "
              f"{x['sin_cambios']:>11} {x['cuarentena_nueva']:>15}")
    print(f"Días de venta recalculados: {r['dias_recalculados']}")
    print("Bronze: " + ", ".join(f"{t}={'nuevo' if i['nuevo'] else 'ya existía'}" for t, i in r["bronze"].items()))

    con = duckdb.connect(a.db, read_only=True)
    print("\nCuarentena por tabla y regla (registros distintos):")
    for fila in con.execute("""
        SELECT tabla_origen, regla_violada, count(DISTINCT id_registro) AS registros
        FROM cuarentena GROUP BY 1, 2 ORDER BY 1, 3 DESC""").fetchall():
        print(f"  {fila[0]:9} {fila[1]:28} {fila[2]:>6}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
