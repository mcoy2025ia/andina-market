"""Chequeos reproducibles, sin originales, nube ni API de pago."""
from pathlib import Path
import ast
import json
import subprocess
import sys
from verificar_entrega import verificar
from empaquetar import archivos

ROOT=Path(__file__).resolve().parents[1]


def main():
    archivos()
    for base in ['src','scripts','tests']:
        for p in (ROOT/base).rglob('*.py'):
            ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    notebook=ROOT/'fabric/notebooks/andina_etl_spark.ipynb'
    antes=notebook.read_bytes()
    subprocess.run([sys.executable,str(ROOT/'src/shared/spark/build_notebook.py')],check=True,cwd=ROOT)
    if notebook.read_bytes()!=antes:raise RuntimeError('Notebook desactualizado respecto al generador')
    nb=json.loads(antes)
    for cell in nb['cells']:
        if cell['cell_type']=='code':ast.parse(''.join(cell['source']))
    template=(ROOT/'src/shared/spark/sql/01_ventas_recompra.template.sql').read_text(encoding='utf-8')
    for platform in ['fabric','databricks']:
        if (ROOT/platform/'sql/01_ventas_recompra.sql').read_text(encoding='utf-8')!=template.replace('{S}','silver.'):
            raise RuntimeError(f'SQL generado desactualizado: {platform}')
    verificar(out=ROOT/'.local/ci')


if __name__=='__main__':main()
