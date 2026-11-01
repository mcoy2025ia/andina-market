"""IA-R03: incorporar etiquetas de tipo de caso al almacén, versionadas y con procedencia.

Dos entradas, que no son intercambiables:

  revision    decisiones humanas de la plantilla revisada -> estado REVISADA.
              Es lo único que llega a `gold.fact_ticket.tipo_caso`.
  propuestas  salida de un clasificador (reglas o LLM) -> estado PROPUESTA.
              Queda en `tipo_caso_propuesto` y nunca se presenta como validada.

Ejemplos (desde la raíz del repositorio):
  python scripts/importar_etiquetas.py revision --db data/warehouse.duckdb \\
      --archivo docs/revision_etiquetas_34.csv --version rev-2026-11-01
  python scripts/importar_etiquetas.py propuestas --db data/warehouse.duckdb \\
      --metodo reglas --version reglas-2026-11-01

Tras importar hay que reconstruir los hechos para que la estrella lo recoja:
  python scripts/cargar_datos.py
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src' / 'shared'))

import duckdb  # noqa: E402
from andina_etl import etiquetas  # noqa: E402
from andina_etl.operations import bloqueo  # noqa: E402


def _textos_de_tickets(con) -> list[str]:
    return [t for (t,) in con.execute(
        'SELECT DISTINCT descripcion_original FROM silver_tickets '
        'WHERE descripcion_original IS NOT NULL').fetchall()]


def importar_revision(a) -> dict:
    filas = etiquetas.leer_revision(a.archivo)
    if not filas:
        raise SystemExit(
            f'{a.archivo}: ninguna fila tiene decisión final. La revisión humana (U05) '
            'sigue pendiente; no hay nada que importar como validado.')
    with bloqueo(a.db), duckdb.connect(str(a.db)) as con:
        resultado = etiquetas.importar(con, filas, a.version)
    resultado['filas_sin_decision'] = filas[0].get('_incompletas', 0)
    return resultado


def importar_propuestas(a) -> dict:
    from tickets_ia.reglas import clasificar_reglas
    with duckdb.connect(str(a.db), read_only=True) as con:
        textos = _textos_de_tickets(con)
    if not textos:
        raise SystemExit('No hay tickets cargados: ejecutar antes scripts/cargar_datos.py')

    if a.metodo == 'reglas':
        pares = [(t, clasificar_reglas(t)) for t in textos]
        origen, confianzas = 'reglas', {}
    else:
        from tickets_ia.llm import ClasificadorLLM, crear_llamada_deepseek
        clf = ClasificadorLLM(crear_llamada_deepseek(a.modelo), modelo=a.modelo)
        salidas = clf.clasificar(textos)
        # Una respuesta que el cliente no pudo validar no se importa ni como propuesta.
        pares = [(t, r['tipo']) for t, r in zip(textos, salidas) if r['valido']]
        confianzas = {t: r['confianza'] for t, r in zip(textos, salidas) if r['valido']}
        origen = f'llm:{a.modelo}'

    filas = etiquetas.desde_clasificador(pares, origen, confianzas)
    with bloqueo(a.db), duckdb.connect(str(a.db)) as con:
        resultado = etiquetas.importar(con, filas, a.version)
    resultado['textos_descartados'] = len(textos) - len(pares)
    return resultado


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest='cmd', required=True)

    r = s.add_parser('revision', help='decisiones humanas (estado REVISADA)')
    r.add_argument('--db', required=True)
    r.add_argument('--archivo', required=True)
    r.add_argument('--version', required=True)

    q = s.add_parser('propuestas', help='salida de un clasificador (estado PROPUESTA)')
    q.add_argument('--db', required=True)
    q.add_argument('--version', required=True)
    q.add_argument('--metodo', choices=['reglas', 'llm'], default='reglas')
    q.add_argument('--modelo', default='deepseek-flash')

    a = p.parse_args()
    resultado = (importar_revision if a.cmd == 'revision' else importar_propuestas)(a)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print('\nReconstruir los hechos para que la estrella lo recoja: '
          'python scripts/cargar_datos.py')


if __name__ == '__main__':
    main()
