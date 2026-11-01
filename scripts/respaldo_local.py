"""Respaldo/restauración local en frío bajo el lock de la aplicación."""
import argparse
from pathlib import Path
import shutil
import sys
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/shared'))
import duckdb
from andina_etl.operations import bloqueo


def verificar(path):
    with duckdb.connect(str(path),read_only=True) as c:
        return c.execute('SELECT coalesce(sum(venta_neta),0) FROM gold_venta_neta_diaria').fetchone()[0]


def respaldar(db,destino):
    db,destino=Path(db).resolve(),Path(destino).resolve()
    if db==destino or destino.exists():raise ValueError('El respaldo debe ser un archivo nuevo y distinto')
    with bloqueo(db):
        if Path(str(db)+'.wal').exists():raise RuntimeError('Base con WAL: cerrar/checkpoint antes de copiar')
        esperado=verificar(db)
        destino.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(db,destino)
        if verificar(destino)!=esperado:raise RuntimeError('Respaldo no concilia')
    return {'venta_neta':int(esperado),'verificado':True}


def restaurar(respaldo,destino):
    respaldo,destino=Path(respaldo).resolve(),Path(destino).resolve()
    if destino.exists() or respaldo==destino:
        raise ValueError('Restaurar en destino nuevo; validar antes de sustituir la base activa')
    return respaldar(respaldo,destino)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('accion',choices=['respaldar','restaurar'])
    p.add_argument('origen');p.add_argument('destino');a=p.parse_args()
    print((respaldar if a.accion=='respaldar' else restaurar)(a.origen,a.destino))
