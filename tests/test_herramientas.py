from datetime import date
import csv
import json
from pathlib import Path

import duckdb
import pytest
from andina_etl.pipeline import ejecutar
from reporte_archivo import guardar_bandeja
from scripts.reconciliar_fuentes import comparar
from scripts.respaldo_local import respaldar, restaurar
from scripts.cargar_modelo_sqlserver import cargar
from scripts.revision_etiquetas import plantilla, auditar
from .conftest import datos_base, escribir_csvs


def test_reporte_preview_idempotente_y_corrupcion(tmp_path):
    raw=tmp_path/'raw';db=tmp_path/'wh.duckdb';escribir_csvs(raw,datos_base());ejecutar(raw,db)
    out=tmp_path/'out'
    a=guardar_bandeja(db,date(2025,1,10),out);b=guardar_bandeja(db,date(2025,1,10),out)
    assert a['nuevo'] and not b['nuevo'] and a['id']==b['id']
    assert not a['enviado'] and '90,000' in Path(a['archivo']).read_text(encoding='utf-8')
    with duckdb.connect(str(db)) as c:c.execute("UPDATE gold_venta_neta_diaria SET canal='TIENDA' WHERE fecha='2025-01-10'")
    with pytest.raises(RuntimeError,match='no concilian'):guardar_bandeja(db,date(2025,1,10),out)


def test_reconciliar_no_borra_y_restaura_copia(tmp_path):
    raw=tmp_path/'raw';db=tmp_path/'wh.duckdb';d=datos_base();escribir_csvs(raw,d);ejecutar(raw,db)
    d['pedidos']=[p for p in d['pedidos'] if p['id_pedido']!='P001'];escribir_csvs(raw,d)
    r=comparar(raw,db)
    assert r['tablas']['pedidos']['ids_ausentes_en_fuente']==1 and r['borrados_aplicados']==0
    copia=tmp_path/'backup.duckdb';restaurada=tmp_path/'restaurada.duckdb'
    assert respaldar(db,copia)['venta_neta']==350000
    assert restaurar(copia,restaurada)['venta_neta']==350000
    with pytest.raises(ValueError):restaurar(copia,db)
    assert cargar(restaurada)['filas']['fact_pedido']==5
    with pytest.raises(ValueError):cargar(restaurada,aplicar=True)


def test_revision_humana_no_se_fabrica_y_detecta_fuga(tmp_path):
    out=tmp_path/'revision.csv';assert plantilla(out)['filas']==34
    result=auditar(out)
    assert len(result['filas_pendientes'])==34 and result['estado']=='PENDIENTE'
    with pytest.raises(FileExistsError):plantilla(out)
    with out.open(encoding='utf-8') as f:rows=list(csv.DictReader(f));columns=list(rows[0])
    rows=rows[:2]
    for r in rows:r.update(anotador_1='login_app',anotador_2='login_app',decision_final='login_app')
    rows[1]['descripcion']=rows[0]['descripcion'].upper();rows[1]['particion']='evaluacion'
    with out.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
    assert auditar(out)['fugas_exactas']==[3]


def test_fallo_estrella_no_publica(caso_ext,tmp_path,monkeypatch):
    import andina_etl.pipeline as p
    raw,db=caso_ext;ejecutar(raw,db)
    with duckdb.connect(str(db),read_only=True) as c:antes=c.execute('SELECT * FROM publicacion_actual').fetchall()
    def falla(*args):raise RuntimeError('fallo simulado')
    monkeypatch.setattr(p,'refrescar_estrella',falla)
    with pytest.raises(RuntimeError,match='simulado'):ejecutar(raw,db)
    with duckdb.connect(str(db),read_only=True) as c:assert c.execute('SELECT * FROM publicacion_actual').fetchall()==antes


@pytest.fixture
def caso_ext(tmp_path):
    raw=tmp_path/'raw';db=tmp_path/'wh.duckdb';escribir_csvs(raw,datos_base());return raw,db
