"""IA-R05: despacha el reporte diario una sola vez, con reintentos y sin duplicados.

Por defecto el transporte es `bandeja`: escribe el documento en una carpeta y no
abre ninguna conexión. `--transporte smtp` existe pero exige, además, `--autorizar`
y la configuración completa; sin la decisión de U07 (destinatarios, canal y horario)
no debe usarse.

Ejemplos (desde la raíz del repositorio):
  python scripts/despachar_reporte.py --db data/warehouse.duckdb --dia 2026-09-30
  python scripts/despachar_reporte.py --db data/warehouse.duckdb --dia 2026-09-30 --historial
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'shared'))

from reporte_envio import (  # noqa: E402
    Destino, TransporteBandeja, TransporteSMTP, despachar, historial)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--db', required=True)
    p.add_argument('--dia', type=date.fromisoformat)
    p.add_argument('--out', default='.local/reportes')
    p.add_argument('--transporte', choices=['bandeja', 'smtp'], default='bandeja')
    p.add_argument('--para', action='append', default=[], help='destinatario (repetible)')
    p.add_argument('--de', default='', help='remitente')
    p.add_argument('--servidor')
    p.add_argument('--puerto', type=int, default=587)
    p.add_argument('--credencial-en', default='REPORTE_SMTP_PASSWORD',
                   help='nombre de la variable de entorno con la clave; nunca la clave')
    p.add_argument('--reintentos', type=int, default=2)
    p.add_argument('--autorizar', action='store_true',
                   help='confirma que el envío está autorizado (U07)')
    p.add_argument('--historial', action='store_true', help='solo mostrar lo ya despachado')
    a = p.parse_args()

    if a.historial:
        print(json.dumps(historial(a.out), ensure_ascii=False, indent=2))
        return
    if not a.dia:
        p.error('--dia es obligatorio salvo con --historial')

    if a.transporte == 'bandeja':
        # Carpeta local: no hay destinatario real, pero el modelo exige declararlo.
        destino = Destino(destinatarios=tuple(a.para) or ('bandeja-local',),
                          remitente=a.de or 'etl-local', autorizado=True)
        transporte = TransporteBandeja(Path(a.out))
    else:
        if not a.autorizar:
            p.error('--transporte smtp exige --autorizar: sin la decisión de U07 no se envía')
        destino = Destino(destinatarios=tuple(a.para), remitente=a.de, servidor=a.servidor,
                          puerto=a.puerto, variable_credencial=a.credencial_en,
                          autorizado=True)
        transporte = TransporteSMTP()

    resultado = despachar(a.db, a.dia, a.out, destino, transporte, reintentos=a.reintentos)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    if resultado['estado'] == 'FALLIDO':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
