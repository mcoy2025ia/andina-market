"""IA-R03: una etiqueta sin revisar no puede acabar presentada como validada.

La propiedad que estas pruebas defienden no es «el importador funciona», sino que
**no existe un camino** por el que una salida de clasificador llegue a
`gold.fact_ticket.tipo_caso`. Por eso la mayoría son intentos de colarla.
"""
import csv

import duckdb
import pandas as pd
import pytest

from andina_etl import etiquetas
from andina_etl.pipeline import ejecutar
from .conftest import COLS_TICKETS_PRUEBA, datos_base, escribir_csvs, tickets_base

TEXTO = 'El equipo no enciende, quiero cambio'


@pytest.fixture
def caso(tmp_path):
    raw, db = tmp_path / 'raw', tmp_path / 'wh.duckdb'
    escribir_csvs(raw, datos_base())
    filas = tickets_base()
    filas[0]['descripcion'] = TEXTO
    filas[3]['descripcion'] = '  EL EQUIPO NO ENCIENDE,  QUIERO CAMBIO  '   # mismo texto, otra forma
    pd.DataFrame(filas, columns=COLS_TICKETS_PRUEBA).to_csv(raw / 'tickets_soporte.csv', index=False)
    ejecutar(raw, db)
    return raw, db


def consultar(db, sql, params=None):
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql, params or []).fetchall()


def importar(db, filas, version):
    with duckdb.connect(str(db)) as con:
        return etiquetas.importar(con, filas, version)


# ------------------------------------------------------------- normalización

def test_el_mismo_texto_con_otra_forma_comparte_hash():
    assert etiquetas.hash_texto(TEXTO) == etiquetas.hash_texto('  EL EQUIPO NO ENCIENDE,  QUIERO CAMBIO  ')
    assert etiquetas.hash_texto('árbol') == etiquetas.hash_texto('ARBOL')
    # La ñ se pliega como las tildes: es tolerancia a cómo se escribió, no a qué dice.
    assert etiquetas.hash_texto('niño') == etiquetas.hash_texto('nino')
    assert etiquetas.hash_texto('pedido roto') != etiquetas.hash_texto('pedido rota')


# ------------------------------------------------ propuestas nunca son válidas

def test_una_propuesta_no_llega_a_tipo_caso(caso):
    raw, db = caso
    filas = etiquetas.desde_clasificador([(TEXTO, 'equipo_no_enciende')], 'reglas')
    assert importar(db, filas, 'reglas-v1')['importadas'] == 1
    ejecutar(raw, db)       # reconstruye los hechos
    fila = consultar(db, "SELECT tipo_caso, tipo_caso_propuesto, clasificacion_estado, "
                         "clasificacion_version FROM gold.fact_ticket WHERE id_ticket='T1'")[0]
    assert fila == (None, 'equipo_no_enciende', 'PROPUESTA', 'reglas-v1')
    # Ningún ticket queda con decisión humana por haber importado propuestas.
    assert consultar(db, 'SELECT count(*) FROM gold.fact_ticket WHERE tipo_caso IS NOT NULL') == [(0,)]


def test_un_clasificador_no_puede_declararse_humano():
    with pytest.raises(etiquetas.ErrorEtiquetas, match='humano'):
        etiquetas.desde_clasificador([(TEXTO, 'equipo_no_enciende')], 'humano')


def test_revisada_con_origen_de_maquina_se_rechaza(caso):
    _, db = caso
    fila = {'texto': TEXTO, 'tipo': 'equipo_no_enciende', 'estado': 'REVISADA',
            'origen': 'llm:deepseek-flash', 'anotadores': 'a | b', 'motivo': 'claro'}
    with pytest.raises(etiquetas.ErrorEtiquetas, match='solo una decisión humana'):
        importar(db, [fila], 'intento')


@pytest.mark.parametrize('cambio,mensaje', [
    ({'anotadores': 'solo_uno', 'anotadores_crudos': ['solo_uno', '']}, 'dos anotadores'),
    ({'motivo': '  '}, 'sin motivo'),
])
def test_revisada_incompleta_se_rechaza(caso, cambio, mensaje):
    _, db = caso
    fila = {'texto': TEXTO, 'tipo': 'equipo_no_enciende', 'estado': 'REVISADA',
            'origen': 'humano', 'anotadores': 'a | b', 'anotadores_crudos': ['a', 'b'],
            'motivo': 'claro', **cambio}
    with pytest.raises(etiquetas.ErrorEtiquetas, match=mensaje):
        importar(db, [fila], 'intento')


def test_tipo_fuera_del_catalogo_se_rechaza(caso):
    _, db = caso
    with pytest.raises(etiquetas.ErrorEtiquetas, match='catálogo'):
        importar(db, etiquetas.desde_clasificador([(TEXTO, 'inventado')], 'reglas'), 'v1')


def test_el_mismo_texto_con_dos_tipos_es_ambiguo(caso):
    _, db = caso
    filas = etiquetas.desde_clasificador(
        [(TEXTO, 'equipo_no_enciende'), (TEXTO.upper(), 'producto_danado')], 'reglas')
    with pytest.raises(etiquetas.ErrorEtiquetas, match='dos tipos distintos'):
        importar(db, filas, 'v1')


# ------------------------------------------------------- decisiones revisadas

def _revisada(texto=TEXTO, tipo='equipo_no_enciende'):
    return {'texto': texto, 'tipo': tipo, 'estado': 'REVISADA', 'origen': 'humano',
            'anotadores': 'ana | beto', 'anotadores_crudos': ['ana', 'beto'],
            'motivo': 'Ambos coinciden', 'particion': 'desarrollo', 'confianza': None}


def test_una_decision_humana_si_llega_a_tipo_caso(caso):
    raw, db = caso
    importar(db, [_revisada()], 'rev-1')
    ejecutar(raw, db)
    fila = consultar(db, "SELECT tipo_caso, clasificacion_estado, clasificacion_version "
                         "FROM gold.fact_ticket WHERE id_ticket='T1'")[0]
    assert fila == ('equipo_no_enciende', 'REVISADA', 'rev-1')
    # El ticket con el mismo texto escrito de otra forma recibe la misma decisión.
    assert consultar(db, "SELECT tipo_caso FROM gold.fact_ticket WHERE id_ticket='T4'") == [
        ('equipo_no_enciende',)]
    # Los tickets con otro texto siguen sin clasificar.
    assert consultar(db, "SELECT tipo_caso FROM gold.fact_ticket WHERE id_ticket='T3'") == [(None,)]


def test_la_revision_gana_sobre_la_propuesta_sin_borrarla(caso):
    raw, db = caso
    importar(db, etiquetas.desde_clasificador([(TEXTO, 'producto_danado')], 'reglas'), 'reglas-v1')
    importar(db, [_revisada()], 'rev-1')
    ejecutar(raw, db)
    fila = consultar(db, "SELECT tipo_caso, tipo_caso_propuesto, clasificacion_estado "
                         "FROM gold.fact_ticket WHERE id_ticket='T1'")[0]
    # Se conservan las dos: así se puede medir a la IA contra la decisión humana.
    assert fila == ('equipo_no_enciende', 'producto_danado', 'REVISADA')


# --------------------------------------------------------- versiones e historia

def test_reimportar_la_misma_version_no_cambia_nada(caso):
    _, db = caso
    filas = etiquetas.desde_clasificador([(TEXTO, 'equipo_no_enciende')], 'reglas')
    importar(db, filas, 'v1')
    antes = consultar(db, 'SELECT texto_hash, version, tipo FROM ticket_clasificacion ORDER BY 1,2')
    importar(db, filas, 'v1')
    assert consultar(db, 'SELECT texto_hash, version, tipo FROM ticket_clasificacion ORDER BY 1,2') == antes


def test_una_version_nueva_manda_y_la_anterior_queda_como_historia(caso):
    raw, db = caso
    importar(db, [_revisada(tipo='equipo_no_enciende')], 'rev-1')
    importar(db, [_revisada(tipo='producto_danado')], 'rev-2')
    ejecutar(raw, db)
    assert consultar(db, "SELECT tipo_caso, clasificacion_version FROM gold.fact_ticket "
                         "WHERE id_ticket='T1'") == [('producto_danado', 'rev-2')]
    assert consultar(db, 'SELECT count(*) FROM ticket_clasificacion') == [(2,)]


def test_la_version_es_obligatoria(caso):
    _, db = caso
    with pytest.raises(etiquetas.ErrorEtiquetas, match='versión'):
        importar(db, etiquetas.desde_clasificador([(TEXTO, 'equipo_no_enciende')], 'reglas'), '  ')


def test_informa_etiquetas_sin_ticket_y_cobertura(caso):
    _, db = caso
    filas = etiquetas.desde_clasificador(
        [(TEXTO, 'equipo_no_enciende'), ('texto que no existe en ningun ticket', 'otro')], 'reglas')
    r = importar(db, filas, 'v1')
    assert r['sin_ticket_asociado'] == 1
    assert r['tickets_cubiertos']['solo_propuesta'] == 2
    assert r['tickets_cubiertos']['con_decision_humana'] == 0


# ----------------------------------------------------- lectura de la plantilla

def test_la_plantilla_a_medio_llenar_no_produce_decisiones(tmp_path):
    ruta = tmp_path / 'revision.csv'
    columnas = ['descripcion', 'propuesta_ia', 'anotador_1', 'anotador_2',
                'decision_final', 'motivo', 'particion']
    with ruta.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerow(dict(descripcion=TEXTO, propuesta_ia='equipo_no_enciende', particion='desarrollo'))
        w.writerow(dict(descripcion='otro texto', propuesta_ia='otro', anotador_1='ana',
                        anotador_2='beto', decision_final='otro', motivo='coinciden',
                        particion='evaluacion'))
    filas = etiquetas.leer_revision(ruta)
    assert len(filas) == 1 and filas[0]['tipo'] == 'otro'
    assert filas[0]['estado'] == 'REVISADA' and filas[0]['origen'] == 'humano'
    assert filas[0]['_incompletas'] == 1


def test_la_plantilla_actual_del_repositorio_sigue_sin_revisar():
    """U05 está pendiente: si alguien la completa, esta prueba lo avisa."""
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[1] / 'docs/revision_etiquetas_34.csv'
    assert etiquetas.leer_revision(ruta) == [], (
        'La plantilla ya tiene decisiones: importarlas con scripts/importar_etiquetas.py '
        'y actualizar el estado de U05.')
