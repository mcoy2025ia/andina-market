"""Genera docs/02_catalogo_calidad.md con los conteos reales de problemas de calidad.

Uso (después de scripts/cargar_datos.py):
    python scripts/catalogo_calidad.py [--raw data/original] [--db data/warehouse.duckdb] [--salida docs/02_catalogo_calidad.md]
Los conteos de cuarentena salen del almacén; los de problemas que se corrigen (en vez de rechazar)
salen directamente de los CSV de origen.
"""
import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "shared"))

from andina_etl import rules  # noqa: E402


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", default=str(RAIZ / "data" / "original"))
    p.add_argument("--db", default=str(RAIZ / "data" / "warehouse.duckdb"))
    p.add_argument("--salida", default=str(RAIZ / "docs" / "02_catalogo_calidad.md"))
    a = p.parse_args()
    raw = Path(a.raw)
    cli = pd.read_csv(raw / "clientes.csv", dtype=str)
    ped = pd.read_csv(raw / "pedidos.csv", dtype=str)
    pag = pd.read_csv(raw / "pagos.csv", dtype=str)
    tic = pd.read_csv(raw / "tickets_soporte.csv", dtype=str)
    con = duckdb.connect(a.db, read_only=True)

    q = {(t, r): n for t, r, n in con.execute(
        "SELECT tabla_origen, regla_violada, count(DISTINCT id_registro) FROM cuarentena GROUP BY 1,2").fetchall()}
    canal_sucio = int((~ped["canal"].isin(["WEB", "APP", "TIENDA"])).sum())
    cliente_desconocido = int((~ped["id_cliente"].isin(set(cli["id_cliente"]))).sum())
    fecha_dmy = int(pag["fecha_pago"].str.fullmatch(r"\d{2}/\d{2}/\d{4}").sum())
    doc_limpio = cli["documento"].map(rules.limpiar_documento)
    doc_sucio = int((cli["documento"] != doc_limpio).sum())
    clientes_dup = int(con.execute(
        "SELECT count(*) - count(DISTINCT id_cliente_maestro) FROM v_cliente_maestro").fetchall()[0][0])
    cre = pd.to_datetime(tic["fecha_creacion"], errors="coerce")
    cie = pd.to_datetime(tic["fecha_cierre"], errors="coerce")
    cierre_antes = int((cie < cre).sum())
    cerrado_sin_cierre = int(((tic["estado"] == "CERRADO") & cie.isna()).sum())
    entregado_sin_pago = int(con.execute("""SELECT count(*) FROM silver_pedidos p WHERE estado='ENTREGADO'
        AND NOT EXISTS (SELECT 1 FROM silver_pagos g WHERE g.id_pedido = p.id_pedido)""").fetchall()[0][0])
    n = lambda t, r: q.get((t, r), 0)

    filas = [
        ("1", "Canal escrito de ocho formas distintas (`app`, `web `, `PAGINA WEB`, `TIENDA FISICA`...)", "pedidos", canal_sucio,
         "Se normaliza a WEB, APP o TIENDA con un mapa explícito; un valor fuera del mapa va a cuarentena (`CANAL_DESCONOCIDO`)."),
        ("2", "Fecha de pago en dos formatos (`yyyy-mm-dd` y `dd/mm/yyyy`)", "pagos", fecha_dmy,
         "Se interpreta cada formato de forma explícita; nunca se deja que pandas adivine (`03/04/2026` es 3 de abril)."),
        ("3", "Documento del cliente con puntos, espacios o ceros a la izquierda", "clientes", doc_sucio,
         "Se limpia a solo dígitos sin ceros iniciales; se conserva el original en `documento_original`."),
        ("4", "Clientes duplicados (mismo documento limpio, distinto `id_cliente`)", "clientes", clientes_dup,
         "Se conservan ambos ids y la vista `v_cliente_maestro` los une en una persona para contarla una sola vez."),
        ("5", "Pedidos con cliente que no existe en `clientes`", "pedidos", cliente_desconocido,
         "Se conservan (la venta es real) con `flag_cliente_desconocido`; el modelo Gold del DDL lo asigna a un cliente DESCONOCIDO."),
        ("6", "Pedidos duplicados con otro `id_pedido` (mismo cliente, fecha-hora, valor y categoría)", "pedidos",
         n("pedidos", "DUPLICADO_LOGICO"), "Se conserva uno (el que ya estaba en Silver, o el menor id) y el resto va a cuarentena."),
        ("7", "Descuento negativo o mayor que el valor bruto", "pedidos", n("pedidos", "DESCUENTO_INVALIDO"), "Cuarentena (`DESCUENTO_INVALIDO`)."),
        ("8", "Valor bruto cero o negativo", "pedidos", n("pedidos", "VALOR_BRUTO_NO_POSITIVO"), "Cuarentena (`VALOR_BRUTO_NO_POSITIVO`)."),
        ("9", "Fecha de pedido fuera del rango del caso (2027)", "pedidos", n("pedidos", "FECHA_FUERA_DE_RANGO"), "Cuarentena (`FECHA_FUERA_DE_RANGO`)."),
        ("10", "Entrega anterior a la fecha del pedido", "pedidos", n("pedidos", "ENTREGA_ANTERIOR_A_PEDIDO"), "Cuarentena (`ENTREGA_ANTERIOR_A_PEDIDO`)."),
        ("11", "Pagos duplicados (mismo pedido, valor y medio; incluso con la fecha en otro formato)", "pagos",
         n("pagos", "DUPLICADO_LOGICO"), "Se conserva uno y el resto va a cuarentena. El conteo es sobre los pagos que pasaron las "
         "demás reglas; sobre el archivo completo, sin filtrar, son más (350 con los datos del caso)."),
        ("12", "Pagos de un pedido que no existe", "pagos", n("pagos", "PAGO_HUERFANO"), "Cuarentena (`PAGO_HUERFANO`)."),
        ("13", "Pagos de un pedido que fue rechazado", "pagos", n("pagos", "PEDIDO_EN_CUARENTENA"),
         "Cuarentena (`PEDIDO_EN_CUARENTENA`); si el pedido se corrige o llega después, el pago se relee y se carga en la siguiente corrida."),
        ("14", "Ticket con fecha de cierre anterior a la de creación", "tickets", cierre_antes,
         "Implementado en la carga local opcional de soporte: se conserva el ticket y `horas_resolucion` queda nula para no promediar tiempos negativos."),
        ("15", "Ticket cerrado sin fecha de cierre", "tickets", cerrado_sin_cierre, "Implementado: se conserva marcado y horas_resolucion queda nula."),
    ]
    out = ["# Catálogo de problemas de calidad de datos", "",
           "Generado por `scripts/catalogo_calidad.py` con los conteos reales de los CSV y del almacén local. "
           "Los conteos de cuarentena son **registros distintos** (un registro con dos problemas cuenta una vez por regla).", "",
           "| # | Problema | Tabla | Registros | Tratamiento |", "|---|---|---|---:|---|"]
    out += [f"| {i} | {d} | {t} | {miles(c)} | {tr} |" for i, d, t, c, tr in filas]
    out += ["", "## Hallazgos de negocio (no son errores de formato, se reportan)", "",
            f"- **{miles(entregado_sin_pago)} pedidos entregados no tienen ningún pago registrado.** Pueden ser pagos no cargados o ventas sin cobrar; no se corrigen, se escalan.",
            f"- {miles(n('pagos', 'PEDIDO_EN_CUARENTENA'))} pagos pertenecen a pedidos que fueron rechazados por calidad; conviene verificar si hubo cobros duplicados.",
            "", "## Alcance", "",
            "Cada regla vive en `src/shared/andina_etl/rules.py` y tiene su prueba en `tests/test_rules.py`. Los problemas 1 a 5 se **corrigen o se marcan**; "
            "del 6 al 13 se **rechazan a cuarentena**, con la fila original completa en JSON para poder revisarla y reprocesarla; "
            "el 14 y el 15 (tickets) están implementados en la carga local opcional. "
            "Hay además reglas de defensa que con estos datos no encuentran casos: ids nulos, ids repetidos en el mismo archivo y fechas ilegibles."]
    Path(a.salida).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out[6:6 + len(filas)]))


if __name__ == "__main__":
    main()
