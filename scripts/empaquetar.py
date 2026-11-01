"""ZIP revisable a partir de archivos Git, con exclusiones y manifiesto SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SECRETOS=[r'sk-[A-Za-z0-9_-]{20,}',r'gh[pousr]_[A-Za-z0-9]{20,}',
          r'-----BEGIN [A-Z ]*PRIVATE KEY-----']
PROHIBIDOS=('data/', '.venv/', 'finanzauto/', '.local/', 'dist/', '.git/', '.vscode/')


def archivos():
    nombres=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    seguros=[]
    for name in filter(None,nombres):
        path=Path(name)
        if name.startswith(PROHIBIDOS) or path.name.startswith('.env') and path.name!='.env.example':
            raise ValueError(f'Archivo privado versionado: {name}')
        if path.suffix.lower() in {'.duckdb','.parquet','.pyc','.lock'}:
            raise ValueError(f'Artefacto local versionado: {name}')
        if path.suffix.lower() in {'.py','.md','.html','.sql','.json','.yml','.yaml','.txt','.ipynb'}:
            s=(ROOT/path).read_text(encoding='utf-8')
            if any(re.search(p,s) for p in SECRETOS):
                raise ValueError(f'Posible secreto en {name}; valor omitido')
        seguros.append(name)
    return sorted(seguros)


def empaquetar(destino):
    names=archivos();manifest={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    destino=Path(destino);destino.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destino,'w',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(ROOT/name,'andina-market/'+name)
        z.writestr('andina-market/MANIFIESTO_SHA256.json',json.dumps(manifest,indent=2))
    print(f'Paquete: {destino.name}; {len(names)} archivos; SHA256 {hashlib.sha256(destino.read_bytes()).hexdigest()}')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',default=str(ROOT/'dist/andina-market.zip'))
    p.add_argument('--verificar',action='store_true')
    a=p.parse_args()
    if a.verificar:print(f'{len(archivos())} archivos versionados revisados')
    else:empaquetar(a.out)
