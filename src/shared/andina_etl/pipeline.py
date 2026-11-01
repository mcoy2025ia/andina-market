"""Orquestación: clientes -> pedidos -> pagos -> venta neta diaria.

Orden importa: los pagos se validan contra los pedidos ya cargados, y los pedidos
contra los clientes. Toda la corrida es una sola transacción: si el proceso se cae a la
mitad no queda nada a medias (Silver sin Gold) y basta con volver a ejecutarlo. Lo único
que sobrevive a una caída es el Parquet de Bronze, que se vuelve a escribir igual.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from . import bronze, rules, store
from .config import ESTADO_VENTA, Config


def ejecutar(raw_dir: str | Path, db_path: str | Path, cfg: Config | None = None,
             bronze_dir: str | Path | None = None, recalcular_gold: bool = False) -> dict:
    """recalcular_gold: recalcula todos los días de Gold, no solo los tocados. Hace falta
    cuando cambia la definición de venta (por ejemplo, atribuir a fecha_entrega) sin que
    cambien los datos."""
    cfg = cfg or Config()
    raw_dir = Path(raw_dir)
    bronze_dir = Path(bronze_dir) if bronze_dir else Path(db_path).parent / "bronze"
    run_id = str(uuid.uuid4())
    inicio = datetime.now()
    con = store.conectar(str(db_path))
    resumen: dict = {"run_id": run_id, "bronze": {}}

    def fuente(tabla: str) -> pd.DataFrame:
        # CSV -> Bronze (Parquet crudo, inmutable) -> Silver. Silver nunca lee el CSV directo.
        df, info = bronze.aterrizar(con, raw_dir, bronze_dir, tabla, run_id)
        resumen["bronze"][tabla] = info
        return df

    con.begin()
    try:
        # ---- clientes (dimensión pequeña: se lee completa; el hash evita reescrituras)
        cli_raw = fuente("clientes")
        cli_ok, cli_q = rules.validar_clientes(cli_raw, cfg)
        resumen["clientes"], _ = store.upsert(con, "silver_clientes", cli_ok)
        resumen["clientes"]["leidos"] = len(cli_raw)
        resumen["clientes"]["cuarentena_nueva"] = store.registrar_cuarentena(con, cli_q, run_id)
        clientes_ids = set(con.execute("SELECT id_cliente FROM silver_clientes").df()["id_cliente"])

        # ---- pedidos: la fuente no trae fecha de carga, así que el incremental se hace
        # por contenido: solo se escribe lo nuevo o lo que cambió de hash.
        ped_raw = fuente("pedidos")
        ped_ok, ped_q = rules.validar_pedidos(
            ped_raw, cfg, clientes_ids, store.negocio_existente(con, "silver_pedidos"))
        dias_antes = con.execute("SELECT id_pedido, fecha_pedido_dia FROM silver_pedidos").df()
        resumen["pedidos"], ped_escritos = store.upsert(con, "silver_pedidos", ped_ok)
        resumen["pedidos"]["leidos"] = len(ped_raw)
        resumen["pedidos"]["cuarentena_nueva"] = store.registrar_cuarentena(con, ped_q, run_id)
        # Un pedido que ya estaba en Silver y hoy es inválido (dato corregido en la fuente,
        # regla nueva, rango más estrecho) sale de Silver y deja de sumar venta.
        ped_retirados = store.retirar(con, "silver_pedidos", _rechazados(ped_q, ped_ok, "id_pedido"))
        resumen["pedidos"]["retirados"] = len(ped_retirados)

        # Días de venta a recalcular: el día nuevo de cada fila escrita y, si la fila ya
        # existía, también su día anterior (por si el pedido cambió de fecha), más los días
        # de los pedidos retirados.
        fechas_afectadas = _fechas_afectadas(ped_escritos, dias_antes, ped_retirados)

        # ---- pagos: incremental por watermark de fecha_carga, con ventana de reproceso
        pag_raw = fuente("pagos")
        wm = store.leer_watermark(con, "pagos")
        if wm is not None:
            desde = pd.Timestamp(wm) - timedelta(days=cfg.lookback_dias)
            carga = rules._a_fecha(pag_raw["fecha_carga"])
            # Los pagos que esperan a su pedido se releen siempre: si el pedido llega después
            # de que el pago salió de la ventana, de otro modo quedarían huérfanos para siempre.
            pendiente = pag_raw["id_pago"].astype(str).str.strip().isin(store.pagos_pendientes(con))
            pag_raw = pag_raw[(carga >= desde) | carga.isna() | pendiente].reset_index(drop=True)
        pedidos_dia = con.execute(
            "SELECT id_pedido, fecha_pedido_dia FROM silver_pedidos").df().set_index("id_pedido")["fecha_pedido_dia"]
        pedidos_dia = pd.to_datetime(pedidos_dia)
        pag_ok, pag_q = rules.validar_pagos(
            pag_raw, cfg, pedidos_dia, store.ids_en_cuarentena(con, "pedidos"),
            store.negocio_existente(con, "silver_pagos"))
        resumen["pagos"], _ = store.upsert(con, "silver_pagos", pag_ok)
        resumen["pagos"]["leidos"] = len(pag_raw)
        resumen["pagos"]["cuarentena_nueva"] = store.registrar_cuarentena(con, pag_q, run_id)
        resumen["pagos"]["retirados"] = len(store.retirar(con, "silver_pagos", _rechazados(pag_q, pag_ok, "id_pago")))
        if len(pag_raw):
            maximo = rules._a_fecha(pag_raw["fecha_carga"]).max()
            if pd.notna(maximo):
                previo = pd.Timestamp(wm) if wm is not None else maximo
                store.escribir_watermark(con, "pagos", max(maximo, previo).date(), run_id)

        # ---- gold: venta neta diaria solo para los días tocados (o todos, si se pide)
        if recalcular_gold:
            fechas_afectadas = store.dias_con_venta(con)
        resumen["dias_recalculados"] = store.refrescar_venta_neta(con, fechas_afectadas, ESTADO_VENTA)

        _log(con, run_id, inicio, "OK", resumen)
        con.commit()
    except Exception:
        con.rollback()
        _log(con, run_id, inicio, "FALLIDO", resumen)
        raise
    finally:
        con.close()
    return resumen


def _rechazados(cuarentena: pd.DataFrame, validos: pd.DataFrame, clave: str) -> set[str]:
    """Ids que en esta corrida fueron a cuarentena y no quedaron entre los válidos."""
    ids = {i.strip() for i in cuarentena["id_registro"] if i.strip()}
    return ids - set(validos[clave])


def _fechas_afectadas(escritos: pd.DataFrame, dias_antes: pd.DataFrame,
                      retirados: pd.DataFrame | None = None) -> list:
    dias = set()
    if not escritos.empty:
        dias |= set(pd.to_datetime(escritos["fecha_pedido_dia"]).dt.date)
        previos = dias_antes[dias_antes["id_pedido"].isin(escritos["id_pedido"])]
        dias |= set(pd.to_datetime(previos["fecha_pedido_dia"]).dt.date)
    if retirados is not None and not retirados.empty:
        dias |= set(pd.to_datetime(retirados["fecha_pedido_dia"]).dt.date)
    return sorted(dias)


def _log(con, run_id, inicio, estado, resumen):
    def suma(clave):
        return sum(resumen.get(t, {}).get(clave, 0) for t in ("clientes", "pedidos", "pagos"))

    con.execute(
        "INSERT INTO etl_run_log VALUES (?,?,?,?,?,?,?,?,?,?)",
        [run_id, inicio, datetime.now(), estado, suma("leidos"),
         suma("insertados") + suma("actualizados") + suma("sin_cambios"),
         suma("cuarentena_nueva"), suma("insertados"), suma("actualizados"), suma("sin_cambios")],
    )
