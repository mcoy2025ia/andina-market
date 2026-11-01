"""A10: diagnóstico agregado de snapshots; nunca aplica bajas automáticamente."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/shared'))
import duckdb
import pandas as pd
from andina_etl.contracts import validar_archivo
from andina_etl.rules import hash_filas,COLS_CLIENTES,COLS_PEDIDOS,COLS_PAGOS


def comparar(raw,db):
    resultado={}
    with duckdb.connect(str(db),read_only=True) as con:
        for tabla,cols in [('clientes',COLS_CLIENTES),('pedidos',COLS_PEDIDOS),('pagos',COLS_PAGOS)]:
            path=Path(raw)/f'{tabla}.csv';validar_archivo(path,tabla)
            d=pd.read_csv(path,dtype=str,encoding='utf-8-sig',keep_default_na=False,na_values=[''])
            ids=d[cols[0]].fillna('').str.strip();hashes=hash_filas(d,cols)
            base=dict(con.execute(f'SELECT {cols[0]},row_hash FROM silver_{tabla}').fetchall())
            ambiguos=set(ids[ids.duplicated(keep=False)])
            origen=dict(zip(ids,hashes))
            resultado[tabla]={'ids_ausentes_en_fuente':len(set(base)-set(origen)),
                'ids_nuevos_o_en_cuarentena':len(set(origen)-set(base)),
                'ids_ambiguos':len(ambiguos),
                'ids_con_contenido_distinto':sum(base[k]!=origen[k] for k in set(base)&set(origen)-ambiguos)}
    return {'modo':'solo_diagnostico','borrados_aplicados':0,'tablas':resultado,
            'aviso':'Ausencia no autoriza baja: confirmar snapshot completo. Releer pagos con --reconciliar.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',required=True);p.add_argument('--db',required=True)
    a=p.parse_args();print(json.dumps(comparar(a.raw,a.db),ensure_ascii=False,indent=2))
