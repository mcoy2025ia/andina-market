"""Contratos estructurales: un archivo inválido bloquea la corrida, no sus filas."""
import csv
from pathlib import Path

from .rules import COLS_CLIENTES, COLS_PAGOS, COLS_PEDIDOS

COLS_TICKETS = ['id_ticket', 'id_cliente', 'id_pedido', 'fecha_creacion', 'canal',
                'estado', 'fecha_cierre', 'descripcion']
CONTRATOS = dict(clientes=COLS_CLIENTES, pedidos=COLS_PEDIDOS,
                 pagos=COLS_PAGOS, tickets_soporte=COLS_TICKETS)


class ErrorContrato(ValueError):
    pass


def validar_archivo(path: Path, tabla: str) -> dict:
    """UTF-8 (BOM permitido), cabecera única, columnas requeridas y ancho constante.

    Las columnas adicionales se conservan en Bronze y se reportan. Un archivo con
    cabecera sin filas es válido: las compuertas deciden si es publicable.
    No se incluyen valores de las filas en los mensajes de error.
    """
    try:
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f, strict=True)
            headers = next(reader, [])
            if not headers or len(headers) != len(set(headers)):
                raise ErrorContrato(f'{tabla}: cabecera vacía o repetida')
            missing = sorted(set(CONTRATOS[tabla]) - set(headers))
            if missing:
                raise ErrorContrato(f'{tabla}: faltan columnas {missing}')
            rows = 0
            for n, row in enumerate(reader, 2):
                if len(row) != len(headers):
                    raise ErrorContrato(f'{tabla}: ancho inválido en registro {n}')
                rows += 1
        return {'filas': rows, 'extras': sorted(set(headers) - set(CONTRATOS[tabla]))}
    except (UnicodeError, csv.Error) as e:
        raise ErrorContrato(f'{tabla}: codificación o estructura CSV inválida') from e
