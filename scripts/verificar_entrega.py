"""A02: verificación aislada. Nunca reconstruye data/warehouse.duckdb."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/shared'),str(ROOT)]
import duckdb
from andina_etl.pipeline import ejecutar
from tests.conftest import datos_base, escribir_csvs


def verificar(raw=None, out=ROOT/'docs/evidencia/ejecucion_actual', caso=False, pruebas=True):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    result={'fecha_utc':datetime.now(timezone.utc).isoformat(),
            'python':platform.python_version(),'sistema':platform.system(),
            'versiones':{x:importlib.metadata.version(x) for x in ['pandas','duckdb','pytest']},
            'datos':'caso' if caso else ('fuente_local' if raw else 'sinteticos')}
    env=dict(os.environ, PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    if pruebas:
        p=subprocess.run([sys.executable,'-m','pytest','-q','-ra',f'--junitxml={out / "pytest.xml"}'],
                         cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/'pytest.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
        result['pytest_exit_code']=p.returncode
        if p.returncode:
            raise RuntimeError(f'Pruebas fallidas; consultar {out / "pytest.txt"}')
    with tempfile.TemporaryDirectory(prefix='andina-verificacion-') as tmp:
        tmp=Path(tmp)
        if raw is None:
            raw=tmp/'raw';escribir_csvs(raw,datos_base())
        raw=Path(raw).resolve();db=tmp/'modelo.duckdb'
        r1=ejecutar(raw,db)
        def foto():
            with duckdb.connect(str(db),read_only=True) as c:
                return {t:c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in
                        ['silver_clientes','silver_pedidos','silver_pagos','gold_venta_neta_diaria']}, {
                    t:hashlib.sha256(repr(c.execute(f'SELECT * FROM {t} ORDER BY ALL').fetchall()).encode()).hexdigest()
                    for t in ['gold.fact_pedido','gold.fact_pago','gold.fact_venta_neta_diaria']}
        counts,h1=foto();r2=ejecutar(raw,db);_,h2=foto()
        assert h1==h2,'Hechos cambian en segunda carga'
        assert all(r2[t]['insertados']==r2[t]['actualizados']==0 for t in ['clientes','pedidos','pagos'])
        assert all(not info['nuevo'] for info in r2['bronze'].values())
        result.update(conteos=counts,venta_neta=r2['publicacion']['venta_neta'],
                      segunda_carga_sin_cambios=True,hash_hechos=h2,
                      estrella=r2['estrella'],publicacion=r2['publicacion'])
        if caso:
            assert counts==dict(silver_clientes=6040,silver_pedidos=19270,silver_pagos=20124,gold_venta_neta_diaria=7925)
            assert result['venta_neta']==14177333600
        for nombre,r in [('primera_carga',r1),('segunda_carga',r2)]:
            # Las rutas temporales y los hashes de archivos fuente no aportan evidencia pública.
            limpio={k:v for k,v in r.items() if k!='bronze'}
            (out/f'{nombre}.json').write_text(json.dumps(limpio,ensure_ascii=False,indent=2),encoding='utf-8')
        if (raw/'tickets_soporte.csv').exists():
            p=subprocess.run([sys.executable,str(ROOT/'scripts/recalculo_independiente.py'),str(raw)],
                             env=env,capture_output=True,text=True,encoding='utf-8')
            (out/'recalculo_independiente.json').write_text(p.stdout,encoding='utf-8')
            if p.returncode:
                raise RuntimeError('Recálculo independiente falló')
            independiente=json.loads(p.stdout)
            assert independiente['venta_neta_total']==result['venta_neta']
            assert independiente['pedidos']['pedidos_validos']==counts['silver_pedidos']
            result['recalculo_independiente']='venta y pedidos conciliados con pandas independiente'
    (out/'resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw',type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'docs/evidencia/ejecucion_actual')
    p.add_argument('--caso',action='store_true')
    args=p.parse_args()
    if args.caso and not args.raw:p.error('--caso requiere --raw')
    verificar(args.raw,args.out,args.caso)
