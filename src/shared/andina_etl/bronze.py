"""Capa Bronze: copia cruda de la fuente en Parquet, sin limpiar ni tipar.

Reglas de la capa:
  - Todas las columnas de la fuente se guardan como texto, exactamente como llegan.
  - Se agregan columnas de trazabilidad: _ingested_at, _run_id, _source_file, _source_sha256.
  - Es inmutable: nunca se modifica un archivo Bronze ya escrito.
  - Es idempotente: si el archivo de origen tiene el mismo contenido (sha256) que uno ya
    aterrizado, no se escribe nada nuevo y Silver lee la copia existente.

En producción las fuentes son APIs y SQL Server; allí Bronze recibe el incremento de cada
corrida (un archivo por lote). Aquí la fuente es un CSV completo, así que cada versión
distinta del archivo es un snapshot.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from .contracts import validar_archivo

META = ["_ingested_at", "_run_id", "_source_file", "_source_sha256"]

ESQUEMA_BRONZE = """
CREATE TABLE IF NOT EXISTS bronze_manifest (
    tabla        VARCHAR NOT NULL,
    sha256       VARCHAR NOT NULL,
    ruta         VARCHAR NOT NULL,
    filas        INTEGER NOT NULL,
    run_id       VARCHAR NOT NULL,
    ingested_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (tabla, sha256)
);
"""


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _leer_csv_crudo(ruta: Path) -> pd.DataFrame:
    return pd.read_csv(ruta, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""])


def aterrizar(con: duckdb.DuckDBPyConnection, raw_dir: Path, bronze_dir: Path,
              tabla: str, run_id: str) -> tuple[pd.DataFrame, dict]:
    """Aterriza <tabla>.csv en Bronze (si es contenido nuevo) y devuelve lo que hay en Bronze.

    Devuelve (DataFrame con las columnas de la fuente, info). Silver parte siempre de este
    DataFrame, no del CSV: así lo que se transforma es exactamente lo que quedó guardado."""
    con.execute(ESQUEMA_BRONZE)
    origen = raw_dir / f"{tabla}.csv"
    contrato = validar_archivo(origen, tabla)
    sha = sha256_archivo(origen)
    filas = con.execute("SELECT ruta FROM bronze_manifest WHERE tabla = ? AND sha256 = ?", [tabla, sha]).fetchall()

    if filas:
        ruta, nuevo = filas[0][0], False
    else:
        df = _leer_csv_crudo(origen)
        ahora = datetime.now()
        df["_ingested_at"] = ahora
        df["_run_id"] = run_id
        df["_source_file"] = origen.name
        df["_source_sha256"] = sha
        destino = bronze_dir / tabla / f"ingest_date={ahora:%Y-%m-%d}" / f"{tabla}_{sha[:12]}.parquet"
        destino.parent.mkdir(parents=True, exist_ok=True)
        con.register("bronze_stg", df)
        con.execute(f"COPY bronze_stg TO '{destino.as_posix().replace(chr(39), chr(39)*2)}' (FORMAT parquet, COMPRESSION zstd)")
        con.unregister("bronze_stg")
        con.execute("INSERT INTO bronze_manifest VALUES (?,?,?,?,?,?)",
                    [tabla, sha, str(destino), len(df), run_id, ahora])
        ruta, nuevo = str(destino), True

    # hive_partitioning=false: la carpeta ingest_date=... existe para Spark y Fabric, pero aquí
    # no queremos que DuckDB la convierta en una columna más de la fuente.
    leido = con.execute(
        f"SELECT * EXCLUDE ({', '.join(META)}) FROM read_parquet(?, hive_partitioning = false)", [ruta]).df()
    return leido, {"ruta": ruta, "nuevo": nuevo, "sha256": sha, "filas": len(leido), "contrato": contrato}
