"""Datos de prueba pequeños, con cada tipo de error sembrado a propósito."""
from __future__ import annotations

import os
import shutil
import sys

import pandas as pd
import pytest

from andina_etl.rules import COLS_CLIENTES, COLS_PAGOS, COLS_PEDIDOS

OTRO = "CLXXXXXXX"  # cliente que no existe en clientes


def motivo_para_omitir_spark(escribe_archivos: bool = False) -> str | None:
    """Por qué no se puede correr Spark local aquí (None si se puede)."""
    if shutil.which("java") is None:
        return "Java no disponible"
    if os.name == "nt" and sys.version_info >= (3, 12):
        # Observado con PySpark 3.5.3: 'Python worker exited unexpectedly (crashed)'. Con 3.11 pasa.
        return "en Windows, PySpark 3.5 necesita Python 3.11 (con 3.12 se cae el worker de Python)"
    if escribe_archivos and os.name == "nt" and not os.environ.get("HADOOP_HOME"):
        return "en Windows, escribir tablas con Spark necesita winutils.exe y HADOOP_HOME"
    return None


def _fila(cols, *valores):
    return dict(zip(cols, valores))


def datos_base() -> dict[str, list[dict]]:
    c = lambda *v: _fila(COLS_CLIENTES, *v)  # noqa: E731
    p = lambda *v: _fila(COLS_PEDIDOS, *v)  # noqa: E731
    g = lambda *v: _fila(COLS_PAGOS, *v)  # noqa: E731
    return {
        "clientes": [
            c("CL0000001", "Ana Perez", "111111111", "Bogotá", "APP", "2025-01-05"),
            c("CL0000002", "Beto Ruiz", "222.222.222", "Cali", "WEB", "2025-01-20"),
            c("CL0000003", "Ana Perez", " 0111111111 ", "Bogotá", "APP", "2025-01-05"),  # mismo documento
        ],
        "pedidos": [
            # válidos
            p("P001", "CL0000001", "2025-01-10 10:00:00", "app ", "Moda", "100000", "10000", "ENTREGADO", "2025-01-12"),
            p("P002", "CL0000001", "2025-01-10 11:00:00", "WEB", "Hogar", "50000", "0", "CANCELADO", None),
            p("P003", "CL0000002", "2025-02-01 09:00:00", "PAGINA WEB", "Moda", "200000", "20000", "ENTREGADO", "2025-02-03"),
            p("P008", OTRO, "2025-03-03 09:00:00", "WEB", "Moda", "80000", "0", "ENTREGADO", "2025-03-05"),
            p("P010", "CL0000001", "2025-03-04 09:00:00", "APP", "Moda", "60000", "0", "DEVUELTO", "2025-03-06"),
            # con error
            p("P004", "CL0000001", "2025-01-10 10:00:00", "App", "Moda", "100000", "10000", "ENTREGADO", "2025-01-12"),
            p("P005", "CL0000002", "2027-12-22 10:00:00", "APP", "Moda", "100000", "0", "ENTREGADO", "2026-02-05"),
            p("P006", "CL0000001", "2025-03-01 09:00:00", "TIENDA", "Moda", "-5000", "0", "ENTREGADO", "2025-03-01"),
            p("P007", "CL0000002", "2025-03-02 09:00:00", "TIENDA", "Hogar", "100000", "150000", "ENTREGADO", "2025-03-04"),
            p("P009", "CL0000002", "2025-03-02 12:00:00", "MARTE", "Hogar", "100000", "0", "ENTREGADO", "2025-03-04"),
        ],
        "pagos": [
            # válidos
            g("G001", "P001", "2025-01-10", "90000", "PSE", "2025-01-11"),
            g("G003", "P003", "2025-02-01", "180000", "Tarjeta crédito", "2025-02-02"),
            g("G006", "P010", "2025-03-07", "-60000", "PSE", "2025-03-08"),
            # con error
            g("G002", "P001", "10/01/2025", "90000", "PSE", "2025-01-12"),       # mismo pago, otro formato de fecha
            g("G004", "PNOEXISTE", "2025-02-01", "5000", "PSE", "2025-02-02"),   # huérfano
            g("G005", "P004", "2025-01-10", "90000", "PSE", "2025-01-11"),       # pedido en cuarentena
            g("G007", "P003", "2025-01-15", "100", "PSE", "2025-01-16"),         # antes del pedido
            g("G008", "P003", "2025-02-02", "0", "PSE", "2025-02-03"),           # valor cero
            g("G009", "P003", "31/02/2025", "500", "PSE", "2025-02-04"),         # fecha imposible
        ],
    }


COLS_TICKETS_PRUEBA = ["id_ticket", "id_cliente", "id_pedido", "fecha_creacion", "canal",
                       "estado", "fecha_cierre", "descripcion"]


def tickets_base() -> list[dict]:
    """Soporte con cada caso sembrado: cierre coherente, cierre anterior a la creación,
    cerrado sin fecha, abierto, id nulo, id repetido y fecha de creación ilegible."""
    t = lambda *v: _fila(COLS_TICKETS_PRUEBA, *v)  # noqa: E731
    return [
        t("T1", "CL0000001", "P001", "2025-01-10", "CHAT", "CERRADO", "2025-01-11", "Llegó roto"),
        t("T2", "CL0000001", "P001", "2025-01-10", "CHAT", "CERRADO", "2025-01-09", "Cierre invertido"),
        t("T3", "CL0000002", "P003", "2025-02-01", "TELEFONO", "CERRADO", None, "Cerrado sin fecha"),
        t("T4", "CL0000002", "P003", "2025-02-02 09:30:00", "CORREO", "ABIERTO", None, "Sigue abierto"),
        t("T5", OTRO, None, "2025-03-01", "CHAT", "ABIERTO", None, "Cliente desconocido"),
        t(None, "CL0000001", "P001", "2025-01-12", "CHAT", "ABIERTO", None, "Sin id"),
        t("T7", "CL0000001", "P001", "2025-01-13", "CHAT", "ABIERTO", None, "Id repetido"),
        t("T7", "CL0000001", "P001", "2025-01-14", "CHAT", "ABIERTO", None, "Id repetido otra vez"),
        t("T9", "CL0000001", "P001", "31/02/2025", "CHAT", "ABIERTO", None, "Fecha imposible"),
    ]


def escribir_csvs(carpeta, datos: dict[str, list[dict]]) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    columnas = {"clientes": COLS_CLIENTES, "pedidos": COLS_PEDIDOS, "pagos": COLS_PAGOS}
    for nombre, filas in datos.items():
        pd.DataFrame(filas, columns=columnas[nombre]).to_csv(carpeta / f"{nombre}.csv", index=False)


def df_crudo(filas: list[dict], columnas: list[str]) -> pd.DataFrame:
    return pd.DataFrame(filas, columns=columnas, dtype=str)


@pytest.fixture
def datos():
    return datos_base()
