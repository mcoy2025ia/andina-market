"""Almacén DuckDB: esquema, upserts idempotentes, cuarentena y watermark.

Se usa DuckDB para que todo corra desde cero con `pip install`. El esquema y las
claves son los mismos del modelo (ver sql/ddl_tsql.sql para SQL Server / Fabric).
"""
from __future__ import annotations

from datetime import date, datetime

import duckdb
import pandas as pd

ESQUEMA = """
CREATE TABLE IF NOT EXISTS silver_clientes (
    id_cliente         VARCHAR PRIMARY KEY,
    nombre             VARCHAR,
    documento_original VARCHAR,
    documento_limpio   VARCHAR,
    ciudad             VARCHAR,
    canal_registro     VARCHAR,
    fecha_registro     DATE NOT NULL,
    cohorte_registro   DATE,
    row_hash           VARCHAR NOT NULL,
    ingested_at        TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS silver_pedidos (
    id_pedido                VARCHAR PRIMARY KEY,
    id_cliente               VARCHAR,
    fecha_pedido             TIMESTAMP NOT NULL,
    fecha_pedido_dia         DATE NOT NULL,
    canal                    VARCHAR NOT NULL,
    categoria                VARCHAR NOT NULL,
    valor_bruto              BIGINT NOT NULL,
    descuento                BIGINT NOT NULL,
    valor_neto               BIGINT NOT NULL,
    estado                   VARCHAR NOT NULL,
    fecha_entrega            DATE,
    flag_cliente_desconocido BOOLEAN DEFAULT FALSE,
    hash_negocio             VARCHAR,
    row_hash                 VARCHAR NOT NULL,
    ingested_at              TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS silver_pagos (
    id_pago       VARCHAR PRIMARY KEY,
    id_pedido     VARCHAR NOT NULL,
    fecha_pago    DATE NOT NULL,
    valor         BIGINT NOT NULL,
    es_reembolso  BOOLEAN NOT NULL,
    medio_pago    VARCHAR NOT NULL,
    fecha_carga   DATE NOT NULL,
    hash_negocio  VARCHAR,
    row_hash      VARCHAR NOT NULL,
    ingested_at   TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS cuarentena (
    tabla_origen  VARCHAR NOT NULL,
    id_registro   VARCHAR NOT NULL,
    regla_violada VARCHAR NOT NULL,
    row_hash      VARCHAR NOT NULL,
    registro_json VARCHAR NOT NULL,
    run_id        VARCHAR NOT NULL,
    fecha_proceso TIMESTAMP NOT NULL,
    PRIMARY KEY (tabla_origen, id_registro, regla_violada, row_hash)
);

CREATE TABLE IF NOT EXISTS etl_watermark (
    tabla          VARCHAR PRIMARY KEY,
    ultimo_valor   DATE NOT NULL,
    ultimo_run_id  VARCHAR,
    actualizado_en TIMESTAMP
);

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id                    VARCHAR PRIMARY KEY,
    inicio                    TIMESTAMP,
    fin                       TIMESTAMP,
    estado                    VARCHAR,
    filas_leidas              INTEGER,
    filas_validas             INTEGER,
    filas_cuarentena          INTEGER,
    filas_insertadas          INTEGER,
    filas_actualizadas        INTEGER,
    filas_sin_cambios         INTEGER
);

-- Un mismo documento bajo dos id_cliente es la misma persona (40 casos en los datos).
-- Se resuelve con una vista, no con una columna, para que siempre refleje el estado actual.
CREATE OR REPLACE VIEW v_cliente_maestro AS
SELECT id_cliente,
       min(id_cliente) OVER (PARTITION BY coalesce(documento_limpio, id_cliente)) AS id_cliente_maestro
FROM silver_clientes;

CREATE TABLE IF NOT EXISTS gold_venta_neta_diaria (
    fecha        DATE    NOT NULL,
    canal        VARCHAR NOT NULL,
    categoria    VARCHAR NOT NULL,
    num_pedidos  INTEGER NOT NULL,
    venta_bruta  BIGINT  NOT NULL,
    descuento    BIGINT  NOT NULL,
    venta_neta   BIGINT  NOT NULL,
    PRIMARY KEY (fecha, canal, categoria)
);
"""

CLAVES = {
    "silver_clientes": "id_cliente",
    "silver_pedidos": "id_pedido",
    "silver_pagos": "id_pago",
}


def _escalar(con: duckdb.DuckDBPyConnection, sql: str, params=None):
    """Primer valor de la primera fila (o None). Consume todo el resultado para liberar la conexión."""
    filas = con.execute(sql, params or []).fetchall()
    return filas[0][0] if filas else None


def conectar(ruta: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(ruta))
    con.execute(ESQUEMA)
    return con


def upsert(con: duckdb.DuckDBPyConnection, tabla: str,
           df: pd.DataFrame) -> tuple[dict[str, int], pd.DataFrame]:
    """Inserta lo nuevo y reemplaza lo que cambió (distinto row_hash). Lo idéntico no se toca.

    Devuelve (conteos, filas escritas). Es idempotente: ejecutarlo dos veces con el mismo df
    deja la tabla igual, y la segunda vez reporta 0 insertados y 0 actualizados."""
    clave = CLAVES[tabla]
    if df.empty:
        return {"insertados": 0, "actualizados": 0, "sin_cambios": 0}, df

    existente = con.execute(f"SELECT {clave}, row_hash FROM {tabla}").df()
    cruce = df[[clave, "row_hash"]].merge(existente, on=clave, how="left", suffixes=("", "_actual"))
    nuevo = cruce["row_hash_actual"].isna()
    cambiado = ~nuevo & (cruce["row_hash"] != cruce["row_hash_actual"])
    pendientes = df[(nuevo | cambiado).values]

    if len(pendientes):
        columnas = ", ".join(df.columns)
        con.register("stg", pendientes)
        # INSERT OR REPLACE usa la llave primaria: nuevo -> inserta, existente -> reemplaza.
        con.execute(f"INSERT OR REPLACE INTO {tabla} ({columnas}) SELECT {columnas} FROM stg")
        con.unregister("stg")
    conteos = {
        "insertados": int(nuevo.sum()),
        "actualizados": int(cambiado.sum()),
        "sin_cambios": int((~nuevo & ~cambiado).sum()),
    }
    return conteos, pendientes


def registrar_cuarentena(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, run_id: str) -> int:
    """Agrega a cuarentena solo lo que no estaba (misma tabla, id, regla y contenido).
    Reprocesar el mismo archivo no duplica filas."""
    if df.empty:
        return 0
    df = df.drop_duplicates(["tabla_origen", "id_registro", "regla_violada", "row_hash"]).copy()
    df["run_id"] = run_id
    df["fecha_proceso"] = datetime.now()
    antes = _escalar(con, "SELECT count(*) FROM cuarentena")
    con.register("stg_q", df)
    con.execute("""
        INSERT INTO cuarentena
        SELECT s.tabla_origen, s.id_registro, s.regla_violada, s.row_hash, s.registro_json,
               s.run_id, s.fecha_proceso
        FROM stg_q s
        WHERE NOT EXISTS (
            SELECT 1 FROM cuarentena c
            WHERE c.tabla_origen = s.tabla_origen AND c.id_registro = s.id_registro
              AND c.regla_violada = s.regla_violada AND c.row_hash = s.row_hash)
    """)
    con.unregister("stg_q")
    return _escalar(con, "SELECT count(*) FROM cuarentena") - antes


def leer_watermark(con: duckdb.DuckDBPyConnection, tabla: str) -> date | None:
    return _escalar(con, "SELECT ultimo_valor FROM etl_watermark WHERE tabla = ?", [tabla])


def escribir_watermark(con: duckdb.DuckDBPyConnection, tabla: str, valor: date, run_id: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO etl_watermark VALUES (?, ?, ?, ?)",
        [tabla, valor, run_id, datetime.now()],
    )


def negocio_existente(con: duckdb.DuckDBPyConnection, tabla: str) -> dict[str, str]:
    """hash_negocio -> id del registro que ya está en Silver (para detectar duplicados)."""
    clave = CLAVES[tabla]
    filas = con.execute(
        f"SELECT hash_negocio, min({clave}) FROM {tabla} WHERE hash_negocio IS NOT NULL GROUP BY 1"
    ).fetchall()
    return {h: i for h, i in filas}


def ids_en_cuarentena(con: duckdb.DuckDBPyConnection, tabla: str) -> set[str]:
    filas = con.execute(
        "SELECT DISTINCT id_registro FROM cuarentena WHERE tabla_origen = ? AND id_registro <> ''",
        [tabla],
    ).fetchall()
    return {f[0] for f in filas}


def retirar(con: duckdb.DuckDBPyConnection, tabla: str, ids: set[str]) -> pd.DataFrame:
    """Borra de Silver los registros que hoy son inválidos (ya quedaron en cuarentena).
    Devuelve las filas borradas para saber qué días de venta recalcular."""
    clave = CLAVES[tabla]
    if not ids:
        return con.execute(f"SELECT * FROM {tabla} WHERE false").df()
    con.register("ids_retiro", pd.DataFrame({"id": sorted(ids)}))
    filtro = f"{clave} IN (SELECT id FROM ids_retiro)"
    borradas = con.execute(f"SELECT * FROM {tabla} WHERE {filtro}").df()
    con.execute(f"DELETE FROM {tabla} WHERE {filtro}")
    con.unregister("ids_retiro")
    return borradas


def pagos_pendientes(con: duckdb.DuckDBPyConnection) -> set[str]:
    """Pagos que hay que releer aunque estén fuera de la ventana del watermark: los que esperan
    a su pedido (huérfanos o de pedido rechazado) y los de Silver cuyo pedido ya no está."""
    filas = con.execute("""
        SELECT trim(id_registro) FROM cuarentena c
        WHERE tabla_origen = 'pagos' AND regla_violada IN ('PAGO_HUERFANO', 'PEDIDO_EN_CUARENTENA')
          AND NOT EXISTS (SELECT 1 FROM silver_pagos s WHERE s.id_pago = trim(c.id_registro))
        UNION
        SELECT id_pago FROM silver_pagos p
        WHERE NOT EXISTS (SELECT 1 FROM silver_pedidos o WHERE o.id_pedido = p.id_pedido)
    """).fetchall()
    return {f[0] for f in filas}


def dias_con_venta(con: duckdb.DuckDBPyConnection) -> list[date]:
    """Todos los días presentes en Silver o en Gold (para recalcular Gold completo)."""
    filas = con.execute("""
        SELECT fecha_pedido_dia FROM silver_pedidos UNION SELECT fecha FROM gold_venta_neta_diaria
    """).fetchall()
    return [f[0] for f in filas]


def refrescar_venta_neta(con: duckdb.DuckDBPyConnection, fechas: list[date], estado_venta: str) -> int:
    """Recalcula gold_venta_neta_diaria solo para los días afectados por la carga.

    Borra esos días y los vuelve a calcular desde Silver: el resultado depende solo de Silver,
    por eso es idempotente (y si un pedido sale de ENTREGADO, su día se corrige)."""
    if not fechas:
        return 0
    con.register("dias", pd.DataFrame({"fecha": pd.to_datetime(sorted(set(fechas)))}))
    con.execute("DELETE FROM gold_venta_neta_diaria WHERE fecha IN (SELECT CAST(fecha AS DATE) FROM dias)")
    con.execute("""
        INSERT INTO gold_venta_neta_diaria
        SELECT fecha_pedido_dia, canal, categoria,
               count(*)::INTEGER, sum(valor_bruto), sum(descuento), sum(valor_neto)
        FROM silver_pedidos
        WHERE estado = ? AND fecha_pedido_dia IN (SELECT CAST(fecha AS DATE) FROM dias)
        GROUP BY fecha_pedido_dia, canal, categoria
    """, [estado_venta])
    con.unregister("dias")
    return len(set(fechas))
