"""Reglas de calidad en PySpark. Espejo de andina_etl/rules.py (versión pandas/DuckDB).

Mismos códigos de regla, mismo criterio de duplicados, mismo hash de fila sobre los datos
crudos. Sirve para correr en Fabric o Databricks. No depende de Delta: son funciones puras
de DataFrame, por eso se pueden probar con PySpark local.

Todo el parseo usa try_cast / try_to_timestamp: con ANSI activado (por defecto en algunos
runtimes de Databricks) un valor sucio produciría una excepción en vez de NULL.
"""
from __future__ import annotations

from functools import reduce

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

CANALES = {
    "WEB": "WEB", "PAGINA WEB": "WEB",
    "APP": "APP", "APLICACION": "APP",
    "TIENDA": "TIENDA", "TIENDA FISICA": "TIENDA",
}
ESTADOS_PEDIDO = ["ENTREGADO", "DEVUELTO", "CANCELADO"]
MEDIOS_PAGO = ["Tarjeta crédito", "PSE", "Billetera digital", "Contraentrega"]

COLS_CLIENTES = ["id_cliente", "nombre", "documento", "ciudad", "canal_registro", "fecha_registro"]
COLS_PEDIDOS = ["id_pedido", "id_cliente", "fecha_pedido", "canal", "categoria",
                "valor_bruto", "descuento", "estado", "fecha_entrega"]
COLS_PAGOS = ["id_pago", "id_pedido", "fecha_pago", "valor", "medio_pago", "fecha_carga"]


# ---------------------------------------------------------------- utilidades

def _txt(nombre: str) -> Column:
    """Texto sin espacios laterales; vacío -> NULL."""
    limpio = F.trim(F.col(nombre))
    return F.when(limpio == "", F.lit(None)).otherwise(limpio)


def _ts(nombre: str) -> Column:
    """Fecha o fecha-hora ISO; NULL si no se puede leer."""
    return F.coalesce(
        F.expr(f"try_to_timestamp({nombre}, 'yyyy-MM-dd HH:mm:ss')"),
        F.expr(f"try_to_timestamp({nombre}, 'yyyy-MM-dd')"),
    )


def canal_normalizado(nombre: str) -> Column:
    """'app ', 'APLICACION', 'Pagina Web' -> WEB / APP / TIENDA; NULL si no está en el mapa."""
    k = F.upper(F.trim(F.regexp_replace(
        F.translate(F.col(nombre), "ÁÉÍÓÚÜáéíóúü", "AEIOUUaeiouu"), r"\s+", " ")))
    expr = None
    for destino in ("WEB", "APP", "TIENDA"):
        cond = k.isin([c for c, d in CANALES.items() if d == destino])
        expr = F.when(cond, destino) if expr is None else expr.when(cond, destino)
    return expr


def hash_cols(columnas: list[str]) -> Column:
    """sha256 de las columnas crudas unidas con '|' (NULL = ''). Idéntico al de la versión pandas."""
    return F.sha2(F.concat_ws("|", *[F.coalesce(F.col(c), F.lit("")) for c in columnas]), 256)


def documento_limpio(nombre: str) -> Column:
    solo = F.regexp_replace(F.regexp_replace(F.col(nombre), r"\D", ""), r"^0+", "")
    return F.when(solo == "", F.lit(None)).otherwise(solo)


def _alguna(reglas: dict[str, Column]) -> Column:
    return reduce(lambda a, b: a | b, [F.coalesce(c, F.lit(False)) for c in reglas.values()])


def _cuarentena(df: DataFrame, tabla: str, cols_origen: list[str], reglas: dict[str, Column]) -> DataFrame:
    """Una fila por (registro, regla violada), con la fila original completa en JSON."""
    col_id = cols_origen[0]
    partes = [
        df.filter(F.coalesce(cond, F.lit(False))).select(
            F.lit(tabla).alias("tabla_origen"),
            F.coalesce(F.col(col_id), F.lit("")).alias("id_registro"),
            F.lit(codigo).alias("regla_violada"),
            F.col("row_hash"),
            F.to_json(F.struct(*cols_origen), {"ignoreNullFields": "false"}).alias("registro_json"),
        )
        for codigo, cond in reglas.items()
    ]
    return reduce(DataFrame.unionByName, partes)


def _con_veces_id(df: DataFrame, col_id: str) -> DataFrame:
    """Agrega x_veces_id: cuántas veces aparece el id en el lote. Va como columna porque Spark
    no admite funciones de ventana dentro de un filtro."""
    return df.withColumn("x_veces_id", F.count(F.lit(1)).over(Window.partitionBy(col_id)))


def _id_repetido(col_id: str) -> Column:
    """True si el id aparece más de una vez en el lote: todas las copias van a cuarentena."""
    return F.col(col_id).isNotNull() & (F.col("x_veces_id") > 1)


def _desempatar_duplicados(cand: DataFrame, col_id: str, existente: DataFrame) -> DataFrame:
    """Marca x_dup. Gana el que ya está en Silver; si ninguno está, el de menor id."""
    ganador_lote = F.min(col_id).over(Window.partitionBy("hash_negocio"))
    ex = existente.select("hash_negocio", F.col(existente.columns[1]).alias("x_ganador_silver"))
    return (cand.withColumn("x_ganador_lote", ganador_lote)
            .join(ex, "hash_negocio", "left")
            .withColumn("x_dup", F.col(col_id) != F.coalesce(F.col("x_ganador_silver"), F.col("x_ganador_lote"))))


# ------------------------------------------------------------------- clientes

def validar_clientes(raw: DataFrame) -> tuple[DataFrame, DataFrame]:
    df = (raw.withColumn("row_hash", hash_cols(COLS_CLIENTES))
          .withColumn("x_id", _txt("id_cliente"))
          .withColumn("x_fecha", F.expr("try_to_timestamp(fecha_registro, 'yyyy-MM-dd')")))
    n = F.row_number().over(Window.partitionBy("x_id").orderBy("row_hash"))
    df = df.withColumn("x_n", F.when(F.col("x_id").isNotNull(), n))
    reglas = {
        "ID_CLIENTE_NULO": F.col("x_id").isNull(),
        "FECHA_REGISTRO_INVALIDA": F.col("x_fecha").isNull(),
        "ID_CLIENTE_DUPLICADO": F.col("x_n") > 1,
    }
    cuarentena = _cuarentena(df, "clientes", COLS_CLIENTES, reglas)
    ok = df.filter(~_alguna(reglas))
    out = ok.select(
        F.col("x_id").alias("id_cliente"),
        _txt("nombre").alias("nombre"),
        F.col("documento").alias("documento_original"),
        documento_limpio("documento").alias("documento_limpio"),
        _txt("ciudad").alias("ciudad"),
        canal_normalizado("canal_registro").alias("canal_registro"),
        F.col("x_fecha").cast("date").alias("fecha_registro"),
        F.trunc(F.col("x_fecha"), "month").alias("cohorte_registro"),
        F.col("row_hash"),
    )
    return out, cuarentena


# -------------------------------------------------------------------- pedidos

def validar_pedidos(raw: DataFrame, fecha_min: str, fecha_max: str,
                    clientes_ids: DataFrame, negocio_existente: DataFrame) -> tuple[DataFrame, DataFrame]:
    """clientes_ids: DataFrame(id_cliente). negocio_existente: DataFrame(hash_negocio, id_pedido),
    una fila por hash (el id menor ya cargado en Silver)."""
    df = (raw
          .withColumn("row_hash", hash_cols(COLS_PEDIDOS))
          .withColumn("hash_negocio", hash_cols(["id_cliente", "fecha_pedido", "valor_bruto", "categoria"]))
          .withColumn("x_id", _txt("id_pedido"))
          .withColumn("x_cli", _txt("id_cliente"))
          .withColumn("x_canal", canal_normalizado("canal"))
          .withColumn("x_estado", F.upper(_txt("estado")))
          .withColumn("x_fp", _ts("fecha_pedido"))
          .withColumn("x_fe", _ts("fecha_entrega"))
          .withColumn("x_vb", F.expr("try_cast(valor_bruto as double)"))
          .withColumn("x_ds", F.expr("try_cast(descuento as double)"))
          .withColumn("x_dia", F.date_trunc("day", F.col("x_fp"))))
    df = _con_veces_id(df, "x_id")

    fmin, fmax = F.lit(fecha_min).cast("timestamp"), F.lit(fecha_max).cast("timestamp")
    c = F.col
    reglas = {
        "ID_PEDIDO_NULO": c("x_id").isNull(),
        "ID_PEDIDO_DUPLICADO": _id_repetido("x_id"),
        "CANAL_DESCONOCIDO": c("x_canal").isNull(),
        "ESTADO_INVALIDO": ~F.coalesce(c("x_estado").isin(ESTADOS_PEDIDO), F.lit(False)),
        "FECHA_PEDIDO_INVALIDA": c("x_fp").isNull(),
        "FECHA_FUERA_DE_RANGO": c("x_fp").isNotNull() & ((c("x_dia") < fmin) | (c("x_dia") > fmax)),
        "VALOR_BRUTO_NO_POSITIVO": c("x_vb").isNull() | (c("x_vb") <= 0),
        "DESCUENTO_INVALIDO": c("x_ds").isNull() | (c("x_ds") < 0) | (c("x_ds") > c("x_vb")),
        "ENTREGADO_SIN_FECHA": (c("x_estado") == "ENTREGADO") & c("x_fe").isNull(),
        "ENTREGA_ANTERIOR_A_PEDIDO": c("x_fe").isNotNull() & c("x_fp").isNotNull() & (c("x_fe") < c("x_dia")),
    }
    df = df.withColumn("x_malo", _alguna(reglas))
    cand = _desempatar_duplicados(df.filter(~c("x_malo")), "x_id", negocio_existente)

    cuarentena = _cuarentena(df, "pedidos", COLS_PEDIDOS, reglas).unionByName(
        _cuarentena(cand, "pedidos", COLS_PEDIDOS, {"DUPLICADO_LOGICO": c("x_dup")}))

    conocidos = clientes_ids.select(c("id_cliente").alias("x_conocido"), F.lit(True).alias("x_ok"))
    valido = (cand.filter(~c("x_dup"))
              .join(conocidos, c("x_cli") == c("x_conocido"), "left"))
    out = valido.select(
        c("x_id").alias("id_pedido"),
        c("x_cli").alias("id_cliente"),
        c("x_fp").alias("fecha_pedido"),
        c("x_dia").cast("date").alias("fecha_pedido_dia"),
        c("x_canal").alias("canal"),
        _txt("categoria").alias("categoria"),
        c("x_vb").cast("long").alias("valor_bruto"),
        c("x_ds").cast("long").alias("descuento"),
        (c("x_vb") - c("x_ds")).cast("long").alias("valor_neto"),
        c("x_estado").alias("estado"),
        c("x_fe").cast("date").alias("fecha_entrega"),
        c("x_ok").isNull().alias("flag_cliente_desconocido"),
        c("hash_negocio"),
        c("row_hash"),
    )
    return out, cuarentena


# ---------------------------------------------------------------------- pagos

def _fecha_pago() -> Column:
    """yyyy-MM-dd y dd/MM/yyyy con formato explícito: '03/04/2026' es 3 de abril."""
    return F.coalesce(
        F.when(F.col("fecha_pago").rlike(r"^\d{4}-\d{2}-\d{2}$"),
               F.expr("try_to_timestamp(fecha_pago, 'yyyy-MM-dd')")),
        F.when(F.col("fecha_pago").rlike(r"^\d{2}/\d{2}/\d{4}$"),
               F.expr("try_to_timestamp(fecha_pago, 'dd/MM/yyyy')")),
    )


def validar_pagos(raw: DataFrame, pedidos_dia: DataFrame, pedidos_en_cuarentena: DataFrame,
                  negocio_existente: DataFrame) -> tuple[DataFrame, DataFrame]:
    """pedidos_dia: DataFrame(id_pedido, fecha_pedido_dia) de Silver, un id por fila.
    pedidos_en_cuarentena: DataFrame(id_registro) con los ids de pedido rechazados."""
    c = F.col
    pd_ = pedidos_dia.select(c("id_pedido").alias("x_ped"), c("fecha_pedido_dia").cast("timestamp").alias("x_fped"))
    pq = pedidos_en_cuarentena.select(c("id_registro").alias("x_q"), F.lit(True).alias("x_en_q"))
    df = (raw
          .withColumn("row_hash", hash_cols(COLS_PAGOS))
          .withColumn("x_id", _txt("id_pago"))
          .withColumn("x_pedido", _txt("id_pedido"))
          .withColumn("x_fpago", _fecha_pago())
          .withColumn("x_fcarga", F.expr("try_to_timestamp(fecha_carga, 'yyyy-MM-dd')"))
          .withColumn("x_val", F.expr("try_cast(valor as double)"))
          .withColumn("x_medio", _txt("medio_pago"))
          .join(pd_, c("x_pedido") == c("x_ped"), "left")
          .join(pq, c("x_pedido") == c("x_q"), "left"))
    df = _con_veces_id(df, "x_id")
    en_silver = c("x_fped").isNotNull()
    en_q = F.coalesce(c("x_en_q"), F.lit(False))
    reglas = {
        "ID_PAGO_NULO": c("x_id").isNull(),
        "ID_PAGO_DUPLICADO": _id_repetido("x_id"),
        "ID_PEDIDO_NULO": c("x_pedido").isNull(),
        "FECHA_PAGO_INVALIDA": c("x_fpago").isNull(),
        "FECHA_CARGA_INVALIDA": c("x_fcarga").isNull(),
        "VALOR_INVALIDO": c("x_val").isNull() | (c("x_val") == 0),
        "MEDIO_PAGO_INVALIDO": ~F.coalesce(c("x_medio").isin(MEDIOS_PAGO), F.lit(False)),
        "PEDIDO_EN_CUARENTENA": c("x_pedido").isNotNull() & ~en_silver & en_q,
        "PAGO_HUERFANO": c("x_pedido").isNotNull() & ~en_silver & ~en_q,
        "PAGO_ANTERIOR_A_PEDIDO": en_silver & c("x_fpago").isNotNull() & (c("x_fpago") < c("x_fped")),
    }
    df = (df.withColumn("x_malo", _alguna(reglas))
          .withColumn("hash_negocio", F.sha2(F.concat_ws(
              "|", F.coalesce(c("x_pedido"), F.lit("")),
              F.coalesce(F.date_format(c("x_fpago"), "yyyy-MM-dd"), F.lit("")),
              F.coalesce(c("x_val").cast("long").cast("string"), F.lit("")),
              F.coalesce(c("x_medio"), F.lit(""))), 256)))
    cand = _desempatar_duplicados(df.filter(~c("x_malo")), "x_id", negocio_existente)

    cuarentena = _cuarentena(df, "pagos", COLS_PAGOS, reglas).unionByName(
        _cuarentena(cand, "pagos", COLS_PAGOS, {"DUPLICADO_LOGICO": c("x_dup")}))
    out = cand.filter(~c("x_dup")).select(
        c("x_id").alias("id_pago"),
        c("x_pedido").alias("id_pedido"),
        c("x_fpago").cast("date").alias("fecha_pago"),
        c("x_val").cast("long").alias("valor"),
        (c("x_val") < 0).alias("es_reembolso"),
        c("x_medio").alias("medio_pago"),
        c("x_fcarga").cast("date").alias("fecha_carga"),
        c("hash_negocio"),
        c("row_hash"),
    )
    return out, cuarentena
