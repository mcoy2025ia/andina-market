"""IA-R04: el arnés de evaluación sobre muestra reservada.

No se prueba «la IA acierta», que depende de una muestra real que todavía no existe
(U06). Se prueba que el arnés no deja pasar las cosas que harían inválido el informe:
intervalos mal calculados, fugas no detectadas, errores graves contados como leves y
costos inventados.
"""
import json

import pytest

from tickets_ia.evaluacion import (
    DINERO, TIPOS_CRITICOS, errores_criticos, evaluar_reservada, fugas,
    intervalo_wilson, resumen_telemetria, _percentil)
from tickets_ia.llm import ClasificadorLLM


# ------------------------------------------------------------- intervalos

def test_wilson_cubre_los_extremos_sin_salirse_de_cero_uno():
    bajo, alto = intervalo_wilson(0, 20)
    assert bajo == 0.0 and 0 < alto < 0.2
    bajo, alto = intervalo_wilson(20, 20)
    # Acertar todo no significa certeza: el intervalo no puede colapsar a un punto.
    assert alto == 1.0 and 0.8 < bajo < 1.0
    assert intervalo_wilson(0, 0) is None


def test_wilson_coincide_con_el_valor_conocido():
    bajo, alto = intervalo_wilson(94, 150)      # 0,627 sobre 150, el caso del documento
    # Confirma el «0,55 a 0,70» que docs/07_clasificacion_ia.md daba como aproximado.
    assert round(bajo, 3) == 0.547 and round(alto, 3) == 0.700


def test_mas_muestra_estrecha_el_intervalo():
    corto = intervalo_wilson(6, 10)
    largo = intervalo_wilson(600, 1000)
    assert (largo[1] - largo[0]) < (corto[1] - corto[0])


def test_percentil_interpola():
    assert _percentil([1, 2, 3, 4], 0.5) == 2.5
    assert _percentil([5], 0.95) == 5
    assert _percentil([], 0.5) is None


# ------------------------------------------------------------------ fugas

def test_la_fuga_se_detecta_aunque_cambien_mayusculas_tildes_o_espacios():
    desarrollo = ['El equipo no enciende']
    muestra = ['  el EQUIPO  no enciende ', 'El équipo no enciende', 'texto nuevo']
    assert fugas(muestra, desarrollo) == [0, 1]


def test_la_parafrasis_no_se_detecta_y_el_informe_lo_dice():
    informe = evaluar_reservada(['mi aparato no prende'], ['equipo_no_enciende'],
                                ['equipo_no_enciende'], desarrollo=['El equipo no enciende'])
    assert informe['fugas']['cuantas'] == 0
    assert 'no detecta paráfrasis' in informe['fugas']['alcance']


def test_sin_conjunto_de_desarrollo_no_se_afirma_que_la_muestra_sea_valida():
    informe = evaluar_reservada(['x'], ['otro'], ['otro'])
    assert informe['muestra_reservada_valida'] is None
    assert informe['fugas']['comprobado'] is False


# -------------------------------------------------------- errores críticos

@pytest.mark.parametrize('real,predicho,esperado', [
    ('cobro_duplicado', 'producto_danado', 'dinero_mal_enrutado'),
    ('eliminar_cuenta', 'actualizar_datos', None),               # sigue dentro del grupo
    ('eliminar_cuenta', 'login_app', 'derecho_de_datos_perdido'),
    ('pedido_incompleto', 'felicitacion_atencion', 'problema_como_felicitacion'),
    ('cobro_duplicado', 'reembolso_cancelado', None),            # sigue siendo cola de dinero
    ('producto_danado', 'talla_incorrecta', None),               # error leve: reparto de trabajo
])
def test_clasificacion_de_la_gravedad(real, predicho, esperado):
    encontrados = errores_criticos(['texto'], [real], [predicho])
    assert (encontrados[0]['tipo_error'] if encontrados else None) == esperado


def test_un_acierto_nunca_es_error_critico():
    for etiqueta in DINERO:
        assert errores_criticos(['t'], [etiqueta], [etiqueta]) == []


def test_la_definicion_de_critico_se_declara_como_propuesta():
    informe = evaluar_reservada(['t'], ['cobro_duplicado'], ['otro'])
    criticos = informe['errores_criticos']
    assert criticos['conteo']['dinero_mal_enrutado'] == 1
    assert criticos['tasa']['dinero_mal_enrutado'] == 1.0
    assert 'PROPUESTA' in criticos['estado_de_la_definicion']
    assert set(criticos['definicion']) == set(TIPOS_CRITICOS)


# ------------------------------------------------------ costo y latencia

def test_sin_tarifas_no_se_inventa_un_costo():
    r = resumen_telemetria([{'latencia_s': 1.0, 'tokens_entrada': 100, 'tokens_salida': 10}])
    assert r['costo']['calculado'] is False
    assert r['tokens']['total'] == 110
    assert r['latencia_s']['mediana'] == 1.0


def test_con_tarifas_declaradas_se_calcula_y_se_marca_su_origen():
    registros = [{'latencia_s': 0.5, 'tokens_entrada': 1_000_000, 'tokens_salida': 0}]
    r = resumen_telemetria(registros, {'moneda': 'COP', 'entrada': 2000, 'salida': 8000})
    assert r['costo']['total'] == 2000.0
    assert r['costo']['tarifa_declarada_por_el_usuario'] is True


def test_la_latencia_resume_mediana_y_p95():
    registros = [{'latencia_s': v} for v in (0.1, 0.2, 0.3, 10.0)]
    r = resumen_telemetria(registros)
    assert r['latencia_s']['mediana'] == 0.25
    assert r['latencia_s']['maxima'] == 10.0
    assert r['latencia_s']['p95'] > r['latencia_s']['mediana']


def test_el_clasificador_registra_una_medicion_por_llamada_incluidos_los_fallos():
    respuestas = iter([TimeoutError(), '{"tipo":"login_app","confianza":0.9}'])

    def llamada(_):
        x = next(respuestas)
        if isinstance(x, Exception):
            raise x
        llamada.ultimo_uso = {'tokens_entrada': 120, 'tokens_salida': 15}
        return x

    llamada.ultimo_uso = None
    clf = ClasificadorLLM(llamada, dormir=lambda _: None)
    assert clf.clasificar_uno('hola')['valido']
    clf.clasificar_uno('hola')                      # sale de la caché: no mide nada nuevo
    assert len(clf.telemetria) == 2                 # el fallo también cuesta tiempo
    assert [t['exito'] for t in clf.telemetria] == [False, True]
    assert clf.telemetria[1]['tokens_entrada'] == 120
    assert all(t['latencia_s'] >= 0 for t in clf.telemetria)


# ------------------------------------------------------------- informe

def test_el_informe_exige_declarar_la_procedencia():
    informe = evaluar_reservada(['t'], ['otro'], ['otro'])
    assert informe['procedencia_de_la_muestra'] == 'no declarada'
    informe = evaluar_reservada(['t'], ['otro'], ['otro'], procedencia='muestra real de octubre')
    assert informe['procedencia_de_la_muestra'] == 'muestra real de octubre'


@pytest.mark.parametrize('args,mensaje', [
    (([], [], []), 'vacía'),
    ((['a', 'b'], ['otro'], ['otro']), 'mismo tamaño'),
    ((['a'], ['inventado'], ['otro']), 'fuera del catálogo'),
])
def test_el_informe_rechaza_entradas_incoherentes(args, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        evaluar_reservada(*args)


def test_el_informe_trae_intervalos_por_clase_y_es_serializable():
    textos = ['a', 'b', 'c', 'd']
    reales = ['login_app', 'login_app', 'otro', 'otro']
    predichos = ['login_app', 'otro', 'otro', 'otro']
    informe = evaluar_reservada(textos, reales, predichos, desarrollo=[])
    assert informe['exactitud'] == 0.75
    clase = informe['por_clase']['login_app']
    assert clase['recall'] == 0.5
    bajo, alto = clase['intervalo_recall']
    assert bajo < 0.5 < alto
    assert clase['intervalo_precision'] == (pytest.approx(0.207, abs=0.01), 1.0)
    assert informe['clasificados_como_otro_siendo_un_tipo'] == 1
    assert len(informe['errores']) == 1
    json.dumps(informe)          # el informe se guarda tal cual: tiene que serializar
