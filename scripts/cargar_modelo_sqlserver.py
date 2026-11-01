"""A06/E01: plan o recarga transaccional de Gold en SQL Server de pruebas.

Requiere DDL previamente creado, pyodbc y DWH_CONNECTION_STRING. No crea servicios.
Por defecto SOLO muestra conteos; --aplicar --entorno-pruebas permite reemplazar Gold.
Las claves de dimensión del modelo local se preservan mediante IDENTITY_INSERT.
"""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/shared'))
import duckdb

TABLAS=['dim_fecha','dim_canal','dim_categoria','dim_cliente','fact_pedido',
        'fact_pago','fact_ticket','fact_venta_neta_diaria']
IDENTITY={'dim_canal','dim_categoria','dim_cliente'}


def cargar(db,aplicar=False,entorno_pruebas=False):
    if aplicar and not entorno_pruebas:raise ValueError('Confirmar --entorno-pruebas antes de reemplazar Gold')
    with duckdb.connect(str(db),read_only=True) as source:
        plan={t:source.execute(f'SELECT count(*) FROM gold.{t}').fetchone()[0] for t in TABLAS}
        if not aplicar:return {'modo':'plan_sin_conexion','filas':plan}
        import pyodbc
        target=pyodbc.connect(os.environ['DWH_CONNECTION_STRING'],autocommit=False,timeout=30)
        try:
            cursor=target.cursor()
            for t in reversed(TABLAS):cursor.execute(f'DELETE FROM gold.{t}')
            for t in TABLAS:
                rows=source.execute(f'SELECT * FROM gold.{t}')
                cols=[x[0] for x in rows.description]
                sql=f"INSERT INTO gold.{t} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
                if t in IDENTITY:cursor.execute(f'SET IDENTITY_INSERT gold.{t} ON')
                while batch:=rows.fetchmany(1000):cursor.executemany(sql,batch)
                if t in IDENTITY:cursor.execute(f'SET IDENTITY_INSERT gold.{t} OFF')
                real=cursor.execute(f'SELECT count(*) FROM gold.{t}').fetchone()[0]
                if real!=plan[t]:raise RuntimeError(f'Conteo diferente en {t}')
            for t,col in [('fact_pedido','venta_neta'),('fact_venta_neta_diaria','venta_neta'),('fact_pago','valor')]:
                real=cursor.execute(f'SELECT COALESCE(SUM({col}),0) FROM gold.{t}').fetchone()[0]
                esperado=source.execute(f'SELECT coalesce(sum({col}),0) FROM gold.{t}').fetchone()[0]
                if real!=esperado:raise RuntimeError(f'Total diferente en {t}')
            target.commit()
            return {'modo':'aplicado_sqlserver','filas':plan}
        except Exception:
            target.rollback();raise
        finally:target.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',required=True)
    p.add_argument('--aplicar',action='store_true');p.add_argument('--entorno-pruebas',action='store_true')
    a=p.parse_args();print(cargar(a.db,a.aplicar,a.entorno_pruebas))
