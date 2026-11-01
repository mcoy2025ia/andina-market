"""A14: reporte local y bandeja simulada; este módulo nunca envía correos."""
import hashlib
import html
import json
import os
from pathlib import Path

import duckdb
from andina_etl.operations import bloqueo, validar_publicacion


def preparar(db, dia):
    with duckdb.connect(str(db),read_only=True) as con:
        if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='publicacion_actual'").fetchone()[0]:
            raise RuntimeError('No existe publicación validada')
        publicacion=con.execute('SELECT run_id,venta_neta FROM publicacion_actual WHERE id=1').fetchone()
        if not publicacion:raise RuntimeError('No existe publicación validada')
        estado=validar_publicacion(con,{})
        if publicacion[1]!=estado['venta_neta']:raise RuntimeError('La publicación fue modificada después de validar')
        filas=dict((c,(int(v),int(n))) for c,v,n in con.execute(
            'SELECT canal,sum(venta_neta),sum(num_pedidos) FROM gold_venta_neta_diaria WHERE fecha=? GROUP BY canal',
            [dia]).fetchall())
    detalle=[dict(canal=c,venta=filas.get(c,(0,0))[0],pedidos=filas.get(c,(0,0))[1])
             for c in sorted(set(filas)|{'APP','WEB','TIENDA'})]
    contenido={'fecha':dia.isoformat(),'canales':detalle,'estado':'VALIDADO'}
    identidad=hashlib.sha256(json.dumps(contenido,sort_keys=True).encode()).hexdigest()[:24]
    rows=''.join('<tr><td>'+html.escape(r['canal'])+'</td><td>'+f"{r['venta']:,}"+'</td><td>'+str(r['pedidos'])+
                 '</td><td>'+ (f"{r['venta']/r['pedidos']:,.0f}" if r['pedidos'] else 'Sin pedidos')+'</td></tr>' for r in detalle)
    documento=f'''<!doctype html><html lang="es"><meta charset="utf-8"><title>Ventas {dia}</title>
<style>body{{font:16px Arial;max-width:900px;margin:40px auto;padding:20px;color:#183b36}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:14px;border-bottom:1px solid #ddd}}</style>
<h1>Venta neta · {dia}</h1><p>Vista previa local · valores COP · datos validados</p>
<table><tr><th>Canal</th><th>Venta neta</th><th>Pedidos</th><th>Ticket promedio</th></tr>{rows}</table>
<p>Identificador: {identidad}. Esta vista previa no se envió a destinatarios.</p></html>'''
    return identidad,documento,contenido


def guardar_bandeja(db,dia,destino):
    identidad,documento,contenido=preparar(db,dia)
    destino=Path(destino);destino.mkdir(parents=True,exist_ok=True)
    with bloqueo(destino/'bandeja'):
        path=destino/f'{identidad}.html'
        nuevo=not path.exists()
        if nuevo:
            temporal=path.with_suffix('.tmp')
            try:
                temporal.write_text(documento,encoding='utf-8');os.replace(temporal,path)
            finally:temporal.unlink(missing_ok=True)
    return {'id':identidad,'archivo':str(path),'nuevo':nuevo,'enviado':False,'estado':'VISTA_PREVIA'}
