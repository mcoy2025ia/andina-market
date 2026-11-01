"""Reporte diario de venta neta por canal (versión corregida del PR del analista junior).

Venta neta = valor_bruto - descuento de pedidos ENTREGADO, por fecha_pedido, en hora de Colombia.
Lee la tabla certificada gold.fact_venta_neta_diaria (la misma que alimenta Power BI), no la
tabla cruda dbo.pedidos: ahí los canales llegan con variantes ('app ', 'PAGINA WEB') y hay
pedidos duplicados, y el reporte daría una cifra distinta a la oficial.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

CANALES = ("WEB", "APP", "TIENDA")
ZONA = ZoneInfo("America/Bogota")

# Todo el cálculo ocurre en el motor de base de datos: una consulta, parámetros enlazados
# (sin SQL armado con f-strings) y solo las columnas necesarias (sin SELECT *).
# Gold ya trae solo pedidos ENTREGADO, el canal normalizado y sin duplicados.
CONSULTA = """
SELECT c.canal,
       SUM(v.venta_neta)  AS total,
       SUM(v.num_pedidos) AS pedidos
FROM gold.fact_venta_neta_diaria v
JOIN gold.dim_canal c ON c.canal_key = v.canal_key
WHERE v.fecha_key = ?
GROUP BY c.canal
"""


@dataclass(frozen=True)
class VentaCanal:
    canal: str
    total: int
    pedidos: int

    @property
    def ticket(self) -> int | None:
        """Ticket promedio; None (no 0) si no hubo pedidos, para no mostrar un dato falso."""
        return round(self.total / self.pedidos) if self.pedidos else None


def ventas_por_canal(conn, dia: date) -> dict[str, VentaCanal]:
    """Venta neta y pedidos entregados de `dia`. Todos los canales aparecen, aunque no tengan ventas."""
    cur = conn.cursor()
    cur.execute(CONSULTA, (int(dia.strftime("%Y%m%d")),))  # fecha_key = yyyymmdd
    encontrados = {fila[0]: VentaCanal(fila[0], round(fila[1] or 0), int(fila[2])) for fila in cur.fetchall()}
    return {c: encontrados.get(c, VentaCanal(c, 0, 0)) for c in CANALES}


def conectar():
    """La cadena de conexión viene del entorno (Key Vault / variable de entorno), nunca del código.
    Debe usar un usuario de solo lectura, no 'admin'."""
    import pyodbc
    return pyodbc.connect(os.environ["DWH_CONNECTION_STRING"], timeout=30)


def dia_a_reportar(ahora: datetime | None = None) -> date:
    """Por defecto, el día anterior (cerrado) en hora de Colombia. Un informe de las 7:00 con el
    día en curso sale casi vacío. Supuesto a confirmar con quien pidió el reporte."""
    ahora = ahora or datetime.now(ZONA)
    return (ahora - timedelta(days=1)).date()


def enviar_reporte(dia: date | None = None) -> None:
    dia = dia or dia_a_reportar()
    with closing(conectar()) as conn:
        resultado = ventas_por_canal(conn, dia)
    for canal, v in resultado.items():
        ticket = "sin pedidos" if v.ticket is None else f"{v.ticket:,}"
        log.info("Ventas %s %s: %s (%s pedidos) - ticket: %s", canal, dia, f"{v.total:,}", v.pedidos, ticket)
        # TODO: enviar el correo
    # No se captura nada aquí: si falla, la excepción sube, el proceso termina con error y la
    # herramienta que lo programa (Fabric, cron, Actions) alerta.


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        enviar_reporte()
    except Exception:
        log.exception("El reporte de ventas falló")
        sys.exit(1)
