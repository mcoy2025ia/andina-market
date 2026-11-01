"""Reglas de calidad. Funciones puras: reciben DataFrames crudos (todo texto) y
devuelven (filas válidas ya tipadas, filas a cuarentena). No tocan la base de datos,
por eso se pueden probar sin infraestructura.

Convención de cuarentena: una fila por (registro, regla violada). Un registro con dos
problemas aparece dos veces; para contar registros afectados se usa COUNT(DISTINCT).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

import pandas as pd

from .config import Config

CANALES = {
    "WEB": "WEB",
    "PAGINA WEB": "WEB",
    "APP": "APP",
    "APLICACION": "APP",
    "TIENDA": "TIENDA",
    "TIENDA FISICA": "TIENDA",
}
ESTADOS_PEDIDO = {"ENTREGADO", "DEVUELTO", "CANCELADO"}
MEDIOS_PAGO = {"Tarjeta crédito", "PSE", "Billetera digital", "Contraentrega"}

COLS_CLIENTES = ["id_cliente", "nombre", "documento", "ciudad", "canal_registro", "fecha_registro"]
COLS_PEDIDOS = [
    "id_pedido", "id_cliente", "fecha_pedido", "canal", "categoria",
    "valor_bruto", "descuento", "estado", "fecha_entrega",
]
COLS_PAGOS = ["id_pago", "id_pedido", "fecha_pago", "valor", "medio_pago", "fecha_carga"]

COLS_CUARENTENA = ["tabla_origen", "id_registro", "regla_violada", "row_hash", "registro_json"]


# ---------------------------------------------------------------- utilidades

def _vacio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor is pd.NA


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_canal(valor) -> str | None:
    """'app ', 'APLICACION', 'Pagina Web', 'TIENDA FISICA' -> WEB / APP / TIENDA.
    Devuelve None si el valor no está en el mapa (la fila va a cuarentena)."""
    if _vacio(valor):
        return None
    clave = re.sub(r"\s+", " ", _sin_tildes(str(valor)).strip().upper())
    return CANALES.get(clave)


def limpiar_documento(valor) -> str | None:
    """Deja solo dígitos y quita ceros a la izquierda ('294.814.976' -> '294814976')."""
    if _vacio(valor):
        return None
    digitos = re.sub(r"\D", "", str(valor)).lstrip("0")
    return digitos or None


def hash_texto(partes) -> str:
    texto = "|".join("" if _vacio(p) else str(p) for p in partes)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def hash_filas(df: pd.DataFrame, columnas: list[str]) -> pd.Series:
    """Hash de las columnas tal como llegan de la fuente (sin normalizar).
    Sirve para detectar si un registro cambió entre cargas."""
    valores = [hash_texto(t) for t in df[columnas].itertuples(index=False, name=None)]
    return pd.Series(valores, index=df.index, dtype="object")


def parsear_fecha_pago(serie: pd.Series) -> pd.Series:
    """Acepta yyyy-mm-dd y dd/mm/yyyy con formato explícito.
    Nunca se deja que pandas adivine: '03/04/2026' es 3 de abril, no 4 de marzo."""
    s = serie.astype("object").where(serie.notna(), "").astype(str).str.strip()
    es_iso = s.str.fullmatch(r"\d{4}-\d{2}-\d{2}").fillna(False).astype(bool)
    es_dmy = s.str.fullmatch(r"\d{2}/\d{2}/\d{4}").fillna(False).astype(bool)
    iso = pd.to_datetime(s.where(es_iso), format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(s.where(es_dmy), format="%d/%m/%Y", errors="coerce")
    return iso.fillna(dmy)


def _a_fecha(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, format="ISO8601", errors="coerce")


def _texto(serie: pd.Series) -> pd.Series:
    """Serie de texto sin espacios laterales; los vacíos quedan como NaN."""
    s = serie.astype("object").where(serie.notna(), None)
    s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    return s.map(lambda v: None if v == "" else v)


def _cuarentena(raw: pd.DataFrame, tabla: str, col_id: str, row_hash: pd.Series,
                reglas: dict[str, pd.Series]) -> pd.DataFrame:
    partes = []
    for codigo, mascara in reglas.items():
        if not mascara.any():
            continue
        sub = raw.loc[mascara]
        limpio = sub.astype(object).where(sub.notna(), None)
        partes.append(pd.DataFrame({
            "tabla_origen": tabla,
            "id_registro": [("" if _vacio(v) else str(v)) for v in sub[col_id]],
            "regla_violada": codigo,
            "row_hash": row_hash.loc[mascara].values,
            "registro_json": [json.dumps(r, ensure_ascii=False) for r in limpio.to_dict("records")],
        }))
    if not partes:
        return pd.DataFrame(columns=COLS_CUARENTENA)
    return pd.concat(partes, ignore_index=True)


def _marcar_duplicados(candidatos: pd.DataFrame, col_id: str, col_hash: str,
                       existente: dict[str, str]) -> pd.Series:
    """True para los registros que repiten otro con la misma clave de negocio.

    Gana siempre el que ya está en Silver (así una recarga no cambia al ganador);
    si ninguno está, gana el de menor id. Es determinista: mismo input, mismo resultado."""
    ganador_lote = candidatos.groupby(col_hash)[col_id].transform("min")
    ganador_silver = candidatos[col_hash].map(existente)
    ganador = ganador_silver.where(ganador_silver.notna(), ganador_lote)
    return candidatos[col_id] != ganador


# ------------------------------------------------------------------ clientes

def validar_clientes(raw: pd.DataFrame, cfg: Config | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw.copy()
    row_hash = hash_filas(raw, COLS_CLIENTES)
    df["id_cliente"] = _texto(df["id_cliente"])
    fecha = _a_fecha(df["fecha_registro"])
    reglas = {
        "ID_CLIENTE_NULO": df["id_cliente"].isna(),
        "FECHA_REGISTRO_INVALIDA": fecha.isna(),
        "ID_CLIENTE_DUPLICADO": df["id_cliente"].notna() & df["id_cliente"].duplicated(keep="first"),
    }
    cuarentena = _cuarentena(raw, "clientes", "id_cliente", row_hash, reglas)
    malo = pd.concat(reglas, axis=1).any(axis=1)
    ok = df[~malo]
    doc = ok["documento"].map(limpiar_documento)
    fecha_ok = fecha[~malo].dt.normalize()
    out = pd.DataFrame({
        "id_cliente": ok["id_cliente"],
        "nombre": _texto(ok["nombre"]),
        "documento_original": ok["documento"],
        "documento_limpio": doc,
        "ciudad": _texto(ok["ciudad"]),
        "canal_registro": ok["canal_registro"].map(normalizar_canal),
        "fecha_registro": fecha_ok,
        "cohorte_registro": fecha_ok.dt.to_period("M").dt.to_timestamp(),
        "row_hash": row_hash[~malo],
    })
    return out.reset_index(drop=True), cuarentena


# ------------------------------------------------------------------- pedidos

def validar_pedidos(raw: pd.DataFrame, cfg: Config, clientes_ids: set[str],
                    negocio_existente: dict[str, str] | None = None
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    negocio_existente = negocio_existente or {}
    df = raw.copy()
    row_hash = hash_filas(raw, COLS_PEDIDOS)
    hash_negocio = hash_filas(raw, ["id_cliente", "fecha_pedido", "valor_bruto", "categoria"])
    df["id_pedido"] = _texto(df["id_pedido"])
    df["id_cliente"] = _texto(df["id_cliente"])

    canal = df["canal"].map(normalizar_canal)
    estado = _texto(df["estado"]).str.upper()
    fp = _a_fecha(df["fecha_pedido"])
    fe = _a_fecha(df["fecha_entrega"])
    vb = pd.to_numeric(df["valor_bruto"], errors="coerce")
    ds = pd.to_numeric(df["descuento"], errors="coerce")
    fp_dia = fp.dt.normalize()

    reglas = {
        "ID_PEDIDO_NULO": df["id_pedido"].isna(),
        # Si el mismo id llega dos veces no se sabe cuál versión es la buena: van todas a cuarentena.
        "ID_PEDIDO_DUPLICADO": df["id_pedido"].notna() & df["id_pedido"].duplicated(keep=False),
        "CANAL_DESCONOCIDO": canal.isna(),
        "ESTADO_INVALIDO": ~estado.isin(ESTADOS_PEDIDO),
        "FECHA_PEDIDO_INVALIDA": fp.isna(),
        "FECHA_FUERA_DE_RANGO": fp.notna() & (
            (fp_dia < pd.Timestamp(cfg.fecha_min)) | (fp_dia > pd.Timestamp(cfg.fecha_max))),
        "VALOR_BRUTO_NO_POSITIVO": vb.isna() | (vb <= 0),
        "DESCUENTO_INVALIDO": ds.isna() | (ds < 0) | (ds > vb),
        "ENTREGADO_SIN_FECHA": (estado == "ENTREGADO") & fe.isna(),
        "ENTREGA_ANTERIOR_A_PEDIDO": fe.notna() & fp.notna() & (fe < fp_dia),
    }
    reglas = {k: v.fillna(False).astype(bool) for k, v in reglas.items()}
    individual_malo = pd.concat(reglas, axis=1).any(axis=1)

    # Duplicados lógicos: solo entre los registros que pasaron las demás reglas.
    candidatos = pd.DataFrame({"id_pedido": df["id_pedido"], "hash_negocio": hash_negocio})[~individual_malo]
    dup = pd.Series(False, index=df.index)
    if len(candidatos):
        marca = _marcar_duplicados(candidatos, "id_pedido", "hash_negocio", negocio_existente)
        dup.loc[marca[marca].index] = True
    reglas["DUPLICADO_LOGICO"] = dup

    cuarentena = _cuarentena(raw, "pedidos", "id_pedido", row_hash, reglas)
    malo = individual_malo | dup
    ok = ~malo
    out = pd.DataFrame({
        "id_pedido": df["id_pedido"][ok],
        "id_cliente": df["id_cliente"][ok],
        "fecha_pedido": fp[ok],
        "fecha_pedido_dia": fp_dia[ok],
        "canal": canal[ok],
        "categoria": _texto(df["categoria"])[ok],
        "valor_bruto": vb[ok].astype("int64"),
        "descuento": ds[ok].astype("int64"),
        "valor_neto": (vb[ok] - ds[ok]).astype("int64"),
        "estado": estado[ok],
        "fecha_entrega": fe[ok],
        "flag_cliente_desconocido": ~df["id_cliente"][ok].isin(clientes_ids),
        "hash_negocio": hash_negocio[ok],
        "row_hash": row_hash[ok],
    })
    return out.reset_index(drop=True), cuarentena


# --------------------------------------------------------------------- pagos

def validar_pagos(raw: pd.DataFrame, cfg: Config, pedidos_dia: pd.Series,
                  pedidos_en_cuarentena: set[str],
                  negocio_existente: dict[str, str] | None = None
                  ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """pedidos_dia: fecha_pedido_dia de los pedidos válidos en Silver, indexada por id_pedido."""
    negocio_existente = negocio_existente or {}
    df = raw.copy()
    row_hash = hash_filas(raw, COLS_PAGOS)
    df["id_pago"] = _texto(df["id_pago"])
    df["id_pedido"] = _texto(df["id_pedido"])

    fpago = parsear_fecha_pago(df["fecha_pago"])
    fcarga = _a_fecha(df["fecha_carga"])
    valor = pd.to_numeric(df["valor"], errors="coerce")
    medio = _texto(df["medio_pago"])
    en_silver = df["id_pedido"].isin(pedidos_dia.index)
    # Con Silver vacío, map() devuelve float y la comparación con fechas falla (pandas 3).
    fecha_pedido = (df["id_pedido"].map(pedidos_dia) if len(pedidos_dia)
                    else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]"))

    reglas = {
        "ID_PAGO_NULO": df["id_pago"].isna(),
        "ID_PAGO_DUPLICADO": df["id_pago"].notna() & df["id_pago"].duplicated(keep=False),
        "ID_PEDIDO_NULO": df["id_pedido"].isna(),
        "FECHA_PAGO_INVALIDA": fpago.isna(),
        "FECHA_CARGA_INVALIDA": fcarga.isna(),
        "VALOR_INVALIDO": valor.isna() | (valor == 0),
        "MEDIO_PAGO_INVALIDO": ~medio.isin(MEDIOS_PAGO),
        "PEDIDO_EN_CUARENTENA": df["id_pedido"].notna() & ~en_silver & df["id_pedido"].isin(pedidos_en_cuarentena),
        "PAGO_HUERFANO": df["id_pedido"].notna() & ~en_silver & ~df["id_pedido"].isin(pedidos_en_cuarentena),
        "PAGO_ANTERIOR_A_PEDIDO": en_silver & fpago.notna() & (fpago < fecha_pedido),
    }
    reglas = {k: v.fillna(False).astype(bool) for k, v in reglas.items()}
    individual_malo = pd.concat(reglas, axis=1).any(axis=1)

    hash_negocio = hash_filas(
        pd.DataFrame({"p": df["id_pedido"], "f": fpago.dt.strftime("%Y-%m-%d"), "v": valor, "m": medio}),
        ["p", "f", "v", "m"],
    )
    candidatos = pd.DataFrame({"id_pago": df["id_pago"], "hash_negocio": hash_negocio})[~individual_malo]
    dup = pd.Series(False, index=df.index)
    if len(candidatos):
        marca = _marcar_duplicados(candidatos, "id_pago", "hash_negocio", negocio_existente)
        dup.loc[marca[marca].index] = True
    reglas["DUPLICADO_LOGICO"] = dup

    cuarentena = _cuarentena(raw, "pagos", "id_pago", row_hash, reglas)
    ok = ~(individual_malo | dup)
    out = pd.DataFrame({
        "id_pago": df["id_pago"][ok],
        "id_pedido": df["id_pedido"][ok],
        "fecha_pago": fpago[ok],
        "valor": valor[ok].astype("int64"),
        "es_reembolso": (valor[ok] < 0),
        "medio_pago": medio[ok],
        "fecha_carga": fcarga[ok].dt.normalize(),
        "hash_negocio": hash_negocio[ok],
        "row_hash": row_hash[ok],
    })
    return out.reset_index(drop=True), cuarentena
