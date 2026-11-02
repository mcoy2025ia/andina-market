"""Genera los cuatro CSV sintéticos del caso, para validar plataforma sin datos personales.

Por qué existe: `data/original/*.csv` trae documentos de identidad y texto escrito por
clientes. Subirlos a un workspace en la nube es una decisión con consecuencias de
privacidad, y no hace falta para comprobar que la plataforma funciona: los mecanismos
—contratos, cuarentena, idempotencia, conciliación, publicación— se verifican igual con
estos datos, que llevan cada tipo de error sembrado a propósito.

Lo que sí exige datos reales es contrastar las cifras de referencia del caso
(6.040 / 19.270 / 20.124 / 7.925 y COP 14.177.333.600).

Uso:
  python scripts/generar_csv_sinteticos.py --out .local/sinteticos
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / 'src' / 'shared'), str(RAIZ)]

import pandas as pd  # noqa: E402
from tests.conftest import (  # noqa: E402
    COLS_TICKETS_PRUEBA, datos_base, escribir_csvs, tickets_base)


def generar(destino: Path) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    datos = datos_base()
    escribir_csvs(destino, datos)
    pd.DataFrame(tickets_base(), columns=COLS_TICKETS_PRUEBA).to_csv(
        destino / 'tickets_soporte.csv', index=False)
    return {
        'destino': str(destino.resolve()),
        'archivos': sorted(p.name for p in destino.glob('*.csv')),
        'filas': {'clientes': len(datos['clientes']), 'pedidos': len(datos['pedidos']),
                  'pagos': len(datos['pagos']), 'tickets_soporte': len(tickets_base())},
        'venta_neta_esperada': 350000,
        'aviso': 'Datos sintéticos: sirven para validar mecanismos, no las cifras del caso.',
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', type=Path, default=RAIZ / '.local' / 'sinteticos')
    import json
    print(json.dumps(generar(p.parse_args().out), ensure_ascii=False, indent=2))
