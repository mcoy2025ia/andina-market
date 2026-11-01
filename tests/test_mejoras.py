"""Contratos de negocio y fallos observables: extensiones A04–A17."""
import json
import re
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from andina_etl.contracts import ErrorContrato, validar_archivo
from andina_etl.operations import bloqueo, PoliticaPublicacion, PublicacionBloqueada
from andina_etl.pipeline import ejecutar
from andina_etl.rules import parsear_pesos
from tickets_ia.llm import ClasificadorLLM, interpretar
from .conftest import datos_base, escribir_csvs, OTRO


@pytest.fixture
def caso(tmp_path):
    raw, db = tmp_path/'raw', tmp_path/'wh.duckdb'
    escribir_csvs(raw, datos_base())
    return raw, db


def query(db, sql):
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql).fetchall()


def test_calendario_y_contrato_silver_gold_sql(caso):
    raw, db = caso
    ejecutar(raw, db)
    s = (Path(__file__).parents[1]/'duckdb/01_ventas_recompra.sql').read_text(encoding='utf-8')
    primera = re.sub(r'--[^\n]*', '', s).split(';')[0]
    with duckdb.connect(str(db), read_only=True) as con:
        filas = con.execute(primera).fetchall()
        assert len(filas) == 63
        app = {str(f[0]): f for f in filas if f[1]=='APP'}
        assert app['2025-02-01'][3:] == (0, 90000, -100.0)
        assert app['2025-03-01'][3:] == (0, 0, None)
        assert app['2025-01-01'][4:] == (None, None)
        assert sum(f[3] for f in filas)==350000
        assert con.execute('SELECT sum(venta_neta),count(*) FILTER(WHERE cuenta_como_venta) '
                           'FROM gold.fact_pedido').fetchone()==(350000,3)
        assert con.execute('SELECT sum(venta_neta),sum(num_pedidos) FROM '
                           'gold.fact_venta_neta_diaria').fetchone()==(350000,3)


def test_claves_estables_y_cliente_tardio(caso):
    raw, db = caso
    ejecutar(raw, db)
    antes = query(db,'SELECT * FROM gold.dim_canal ORDER BY 1')
    d = datos_base()
    c = dict(d['clientes'][0],id_cliente=OTRO,documento='999',nombre='Fixture tardio')
    d['clientes'].append(c)
    escribir_csvs(raw,d)
    ejecutar(raw,db)
    assert query(db,'SELECT * FROM gold.dim_canal ORDER BY 1')==antes
    assert query(db,"SELECT flag_cliente_desconocido FROM silver_pedidos WHERE id_pedido='P008'")==[(False,)]
    assert query(db,"SELECT cliente_key>0 FROM gold.fact_pedido WHERE id_pedido='P008'")==[(True,)]


def test_incidencia_se_resuelve_sin_borrar_historia(caso):
    raw,db=caso
    ejecutar(raw,db)
    d=datos_base()
    next(x for x in d['pedidos'] if x['id_pedido']=='P009')['canal']='WEB'
    escribir_csvs(raw,d)
    ejecutar(raw,db)
    assert query(db,"SELECT estado FROM calidad_incidencias WHERE id_registro='P009'")==[('RESUELTA',)]
    assert query(db,"SELECT count(*) FROM cuarentena WHERE id_registro='P009'")==[(1,)]


def test_reconciliacion_relee_pago_antiguo(caso):
    raw,db=caso
    ejecutar(raw,db)
    d=datos_base();d['pagos'][0]['valor']='85000';escribir_csvs(raw,d)
    ejecutar(raw,db)
    assert query(db,"SELECT valor FROM silver_pagos WHERE id_pago='G001'")==[(90000,)]
    ejecutar(raw,db,reconciliar=True)
    assert query(db,"SELECT valor FROM silver_pagos WHERE id_pago='G001'")==[(85000,)]


def test_gate_rollback_y_ultima_publicacion(caso):
    raw,db=caso
    ejecutar(raw,db)
    anterior=query(db,'SELECT * FROM publicacion_actual')
    d=datos_base();d['pedidos'][0]['valor_bruto']='110000';escribir_csvs(raw,d)
    with pytest.raises(PublicacionBloqueada):
        ejecutar(raw,db,politica=PoliticaPublicacion(venta_esperada=350000))
    assert query(db,'SELECT * FROM publicacion_actual')==anterior
    assert query(db,'SELECT sum(venta_neta) FROM gold.fact_pedido')==[(350000,)]
    assert not Path(str(db)+'.lock').exists()


@pytest.mark.parametrize('policy',[
    PoliticaPublicacion(max_fraccion_cuarentena=0.1),
    PoliticaPublicacion(min_pedidos=999),
    PoliticaPublicacion(fecha_minima_datos=date(2026,9,30)),
])
def test_compuertas_configuradas(caso,policy):
    with pytest.raises(PublicacionBloqueada):ejecutar(*caso,politica=policy)


def test_bloqueo_excluye_otro_escritor_y_libera(tmp_path):
    db=tmp_path/'wh.duckdb'
    with bloqueo(db):
        with pytest.raises(RuntimeError,match='lock'):
            with bloqueo(db):pass
    with bloqueo(db):pass


@pytest.mark.parametrize('text',['','id_cliente,id_cliente\na,b\n','id_cliente,nombre\n1,x\n'])
def test_contrato_rechaza_cabecera(tmp_path,text):
    path=tmp_path/'clientes.csv';path.write_text(text,encoding='utf-8')
    with pytest.raises(ErrorContrato):validar_archivo(path,'clientes')


def test_contrato_falla_antes_de_publicar(caso):
    raw,db=caso;ejecutar(raw,db)
    original=query(db,'SELECT * FROM publicacion_actual')
    (raw/'pedidos.csv').write_text('id_pedido\nP001\n',encoding='utf-8')
    with pytest.raises(ErrorContrato):ejecutar(raw,db)
    assert query(db,'SELECT * FROM publicacion_actual')==original


def test_pesos_exactos_y_sin_truncar():
    r=parsear_pesos(pd.Series(['9007199254740993','100.0','100.5','NaN','Infinity',str(2**63)]))
    assert r.iloc[:2].tolist()==[9007199254740993,100]
    assert r.iloc[2:].isna().all()


def test_soporte_conserva_incoherentes_y_excluye_sla(caso):
    raw,db=caso
    cols=['id_ticket','id_cliente','id_pedido','fecha_creacion','canal','estado','fecha_cierre','descripcion']
    pd.DataFrame([
        ['T1','CL0000001','P001','2025-01-10','CHAT','CERRADO','2025-01-09','Ejemplo'],
        ['T2','CL0000001','P001','2025-01-10','CHAT','CERRADO','','Ejemplo'],
        ['T3','CL0000001','P001','2025-01-10','CHAT','CERRADO','2025-01-11','Ejemplo'],
    ],columns=cols).to_csv(raw/'tickets_soporte.csv',index=False)
    ejecutar(raw,db);r=ejecutar(raw,db)
    assert r['tickets_soporte']['insertados']==0
    assert query(db,'SELECT horas_resolucion FROM gold.fact_ticket ORDER BY id_ticket')==[(None,),(None,),(24.0,)]


@pytest.mark.parametrize('conf',[-.1,1.1,float('nan'),float('inf'),True,'0.9'])
def test_confianza_invalida(conf):
    assert interpretar(json.dumps({'tipo':'login_app','confianza':conf}))[2] is False


@pytest.mark.parametrize('respuesta',['[]','null','3','{"tipo": 1}'])
def test_llm_no_objeto(respuesta):assert interpretar(respuesta)[2] is False


def test_llm_transporte_presupuesto_y_cache():
    respuestas=iter([TimeoutError(),'{"tipo":"login_app","confianza":0.9}'])
    def llamada(_):
        x=next(respuestas)
        if isinstance(x,Exception):raise x
        return x
    c=ClasificadorLLM(llamada,max_llamadas=2,dormir=lambda _:None)
    assert c.clasificar_uno('a')['valido']
    assert c.clasificar_uno('a')['valido'] and c.llamadas==2
    assert c.clasificar_uno('b')['error']=='PRESUPUESTO_AGOTADO'


def test_llm_error_permanente_no_reintenta_ni_expone_mensaje():
    def falla(_):raise ValueError('informacion sensible')
    c=ClasificadorLLM(falla,dormir=lambda _:None)
    result=c.clasificar_uno('a')
    assert result['error']=='ERROR_PERMANENTE' and c.llamadas==1
    assert 'sensible' not in str(result)
