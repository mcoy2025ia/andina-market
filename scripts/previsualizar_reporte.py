"""Genera vista previa idempotente en disco, sin correo ni API."""
import argparse
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/shared'))
from reporte_archivo import guardar_bandeja

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',required=True)
    p.add_argument('--dia',required=True,type=date.fromisoformat);p.add_argument('--out',default='.local/reportes')
    a=p.parse_args();print(guardar_bandeja(a.db,a.dia,a.out))
