"""Parámetros del proceso. Todo lo que sea una decisión de negocio vive aquí,
no regado dentro de las reglas."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Config:
    # Rango válido de fecha_pedido. El caso dice: enero 2025 a septiembre 2026.
    fecha_min: date = date(2025, 1, 1)
    fecha_max: date = date(2026, 9, 30)

    # Ventana de reproceso de pagos por fecha_carga. Cubre cargas tardías o
    # re-enviadas por la fuente sin reprocesar todo el histórico.
    lookback_dias: int = 3


# Estado que cuenta como venta (definición del caso: pedidos entregados).
ESTADO_VENTA = "ENTREGADO"
