"""Plantilla y auditoría de anotación humana, sin generar decisiones humanas."""
import argparse
import csv
import json
from pathlib import Path
import sys
import unicodedata
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/shared'))
from tickets_ia.taxonomia import ETIQUETAS

ROOT=Path(__file__).resolve().parents[1]


def normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',texto.casefold())
                           if unicodedata.category(c)!='Mn').split())


def plantilla(destino):
    with (ROOT/'src/shared/tickets_ia/datos/etiquetas_reales.csv').open(encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    # Conservar la propuesta pero no completar ninguna columna de revisión.
    path=Path(destino);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['descripcion','propuesta_ia','anotador_1','anotador_2','decision_final','motivo','particion'])
        w.writeheader()
        for r in rows:
            propuesta=r.get('tipo') or r.get('etiqueta')
            w.writerow(dict(descripcion=r['descripcion'],propuesta_ia=propuesta,particion='desarrollo'))
    return {'filas':len(rows),'estado':'PENDIENTE_REVISION_HUMANA'}


def auditar(path):
    with Path(path).open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    pendientes=[];invalidas=[];fugas=[];seen={};pairs=[]
    for i,r in enumerate(rows,2):
        a,b,final=(r.get(k,'').strip() for k in ['anotador_1','anotador_2','decision_final'])
        if not a or not b or not final:pendientes.append(i)
        elif any(x not in ETIQUETAS for x in (a,b,final)):invalidas.append(i)
        else:pairs.append((a,b))
        partition=r.get('particion','').strip()
        if partition not in {'desarrollo','evaluacion'}:invalidas.append(i)
        key=normalizar(r['descripcion'])
        if key in seen and seen[key]!=partition:fugas.append(i)
        seen[key]=partition
    acuerdo=sum(a==b for a,b in pairs)/len(pairs) if pairs else None
    kappa=None
    if pairs:
        ca,cb=Counter(a for a,b in pairs),Counter(b for a,b in pairs)
        pe=sum(ca[t]*cb[t] for t in set(ca)|set(cb))/len(pairs)**2
        kappa=(acuerdo-pe)/(1-pe) if pe<1 else None
    return dict(filas=len(rows),filas_pendientes=pendientes,filas_invalidas=sorted(set(invalidas)),
                fugas_exactas=fugas,acuerdo=acuerdo,kappa=kappa,
                estado='VALIDADO_FORMATO' if rows and not(pendientes or invalidas or fugas) else 'PENDIENTE',
                advertencia='El formato no acredita autoría humana ni independencia semántica; revisar paráfrasis y procedencia.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('accion',choices=['plantilla','auditar']);p.add_argument('archivo')
    a=p.parse_args();print(json.dumps(plantilla(a.archivo) if a.accion=='plantilla' else auditar(a.archivo),ensure_ascii=False,indent=2))
