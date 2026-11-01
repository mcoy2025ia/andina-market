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

from . import bronze, rules, store, tickets
from .operations import bloqueo, actualizar_incidencias, validar_publicacion
from .star import refrescar_estrella
from .config import ESTADO_VENTA, Config


def ejecutar(raw_dir, db_path, cfg=None, bronze_dir=None, recalcular_gold=False,
             politica=None, reconciliar=False):
    """Escritor exclusivo local. Reconciliar relee pagos, nunca infiere borrados."""
    with bloqueo(db_path):
        return _ejecutar(raw_dir, db_path, cfg, bronze_dir, recalcular_gold, politica, reconciliar)


def _ejecutar(raw_dir: str | Path, db_path: str | Path, cfg: Config | None = None,
             bronze_dir: str | Path | None = None, recalcular_gold: bool = False, politica=None, reconciliar: bool = False) -> dict:
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
        store.retirar(con, "silver_clientes", _rechazados(cli_q, cli_ok, "id_cliente"))
        actualizar_incidencias(con, 'clientes', cli_raw, cli_q, run_id)
        resumen['clientes']['rechazados_lote'] = len(cli_raw) - len(cli_ok)
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

        actualizar_incidencias(con, 'pedidos', ped_raw, ped_q, run_id)
        resumen['pedidos']['rechazados_lote'] = len(ped_raw) - len(ped_ok)
        con.execute("UPDATE silver_pedidos SET flag_cliente_desconocido = NOT EXISTS "
                    "(SELECT 1 FROM silver_clientes c WHERE c.id_cliente=silver_pedidos.id_cliente)")

        # Días de venta a recalcular: el día nuevo de cada fila escrita y, si la fila ya
        # existía, también su día anterior (por si el pedido cambió de fecha), más los días
        # de los pedidos retirados.
        fechas_afectadas = _fechas_afectadas(ped_escritos, dias_antes, ped_retirados)

        # ---- pagos: incremental por watermark de fecha_carga, con ventana de reproceso
        pag_raw = fuente("pagos")
        wm = store.leer_watermark(con, "pagos")
        if wm is not None and not reconciliar:
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
        actualizar_incidencias(con, 'pagos', pag_raw, pag_q, run_id)
        resumen['pagos']['rechazados_lote'] = len(pag_raw) - len(pag_ok)
        if len(pag_raw):
            maximo = rules._a_fecha(pag_raw["fecha_carga"]).max()
            if pd.notna(maximo):
                previo = pd.Timestamp(wm) if wm is not None else maximo
                store.escribir_watermark(con, "pagos", max(maximo, previo).date(), run_id)

        # Soporte es opcional y no altera el cálculo de venta.
        con.execute(tickets.ESQUEMA)
        if (raw_dir / 'tickets_soporte.csv').exists():
            ticket_raw = fuente('tickets_soporte')
            ticket_ok, ticket_q = tickets.validar_tickets(ticket_raw)
            resumen['tickets_soporte'], _ = store.upsert(con, 'silver_tickets', ticket_ok)
            store.retirar(con, 'silver_tickets', _rechazados(ticket_q, ticket_ok, 'id_ticket'))
            resumen['tickets_soporte'].update(leidos=len(ticket_raw),
                rechazados_lote=len(ticket_raw)-len(ticket_ok),
                cuarentena_nueva=store.registrar_cuarentena(con, ticket_q, run_id))
            actualizar_incidencias(con, 'tickets_soporte', ticket_raw, ticket_q, run_id)

        # ---- gold: venta neta diaria solo para los días tocados (o todos, si se pide)
        if recalcular_gold:
            fechas_afectadas = store.dias_con_venta(con)
        resumen["dias_recalculados"] = store.refrescar_venta_neta(con, fechas_afectadas, ESTADO_VENTA)

        resumen['publicacion'] = validar_publicacion(con, resumen, politica)
        resumen['estrella'] = refrescar_estrella(con, cfg)
        con.execute("CREATE TABLE IF NOT EXISTS publicacion_actual "
                    "(id INTEGER PRIMARY KEY, run_id VARCHAR, validado_en TIMESTAMP, venta_neta BIGINT)")
        con.execute("INSERT OR REPLACE INTO publicacion_actual VALUES (1,?,current_timestamp,?)",
                    [run_id, resumen['publicacion']['venta_neta']])
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
        return sum(resumen.get(t, {}).get(clave, 0) for t in ("clientes", "pedidos", "pagos", "tickets_soporte"))

    con.execute(
        "INSERT INTO etl_run_log VALUES (?,?,?,?,?,?,?,?,?,?)",
        [run_id, inicio, datetime.now(), estado, suma("leidos"),
         suma("insertados") + suma("actualizados") + suma("sin_cambios"),
         suma("cuarentena_nueva"), suma("insertados"), suma("actualizados"), suma("sin_cambios")],
    )
