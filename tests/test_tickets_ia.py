"""Pruebas del clasificador de tickets: taxonomía, línea base, métricas y cliente LLM con respuestas simuladas
(no se llama a ninguna API)."""
import csv
import json
from pathlib import Path

import pytest

from tickets_ia import metricas
from tickets_ia.llm import ClasificadorLLM, interpretar
from tickets_ia.reglas import clasificar_reglas, normalizar
from tickets_ia.taxonomia import ETIQUETAS, OTRO, SISTEMA, TIPOS

DATOS = Path(__file__).resolve().parents[1] / "src" / "shared" / "tickets_ia" / "datos"


def _leer(nombre):
    with open(DATOS / nombre, encoding="utf-8", newline="") as f:
        return [(r["descripcion"], r["tipo"]) for r in csv.DictReader(f)]


def test_las_etiquetas_de_los_datos_existen_en_la_taxonomia():
    for nombre in ("etiquetas_reales.csv", "generalizacion.csv"):
        assert {t for _, t in _leer(nombre)} <= set(ETIQUETAS)
    assert len(TIPOS) == 17 and OTRO not in TIPOS
    assert all(t in SISTEMA for t in ETIQUETAS)


def test_linea_base_clasifica_perfecto_las_frases_reales_con_o_sin_mayusculas():
    for texto, tipo in _leer("etiquetas_reales.csv"):
        assert clasificar_reglas(texto) == tipo, texto


def test_la_regla_de_talla_no_se_confunde_con_pantalla():
    assert clasificar_reglas("la pantalla vino rota") != "talla_incorrecta"
    assert clasificar_reglas("me enviaron otra talla") == "talla_incorrecta"
    assert normalizar("  ÁRBOL ") == "arbol"


def test_metricas_con_un_caso_conocido():
    reales = ["a", "a", "b", "b"]
    predichos = ["a", "b", "b", "b"]
    m = metricas.evaluar(reales, predichos, ["a", "b"])
    assert m["exactitud"] == 0.75
    assert m["por_clase"]["a"]["recall"] == 0.5 and m["por_clase"]["a"]["precision"] == 1.0
    assert m["por_clase"]["b"]["precision"] == pytest.approx(2 / 3)
    assert m["matriz"]["a"] == {"a": 1, "b": 1}
    assert metricas.consistencia(["x", "y"], ["x", "z"]) == 0.5


def test_interpretar_respuestas_validas_e_invalidas():
    assert interpretar('{"tipo": "login_app", "confianza": 0.9}') == ("login_app", 0.9, True)
    assert interpretar('{"tipo": "inventado", "confianza": 0.5}') == (OTRO, 0.5, False)
    assert interpretar("   ") == (OTRO, None, False)
    assert interpretar("no es json") == (OTRO, None, False)


def test_cliente_reintenta_si_llega_vacio_y_no_repite_textos_iguales():
    respuestas = iter(["   ", json.dumps({"tipo": "cobro_duplicado", "confianza": 0.95})])
    visto = []

    def falso(mensajes):
        visto.append(mensajes)
        return next(respuestas)

    clf = ClasificadorLLM(falso)
    r = clf.clasificar(["me cobraron doble", "me cobraron doble"])
    assert [x["tipo"] for x in r] == ["cobro_duplicado", "cobro_duplicado"]
    assert clf.llamadas == 2                       # 1 vacía + 1 buena; el texto repetido sale de la caché
    assert "me cobraron doble" in visto[0][1]["content"]
    assert visto[0][0]["role"] == "system"


def test_el_cliente_no_envia_otros_campos_del_ticket():
    visto = []
    clf = ClasificadorLLM(lambda m: visto.append(m) or '{"tipo": "otro", "confianza": 0.1}')
    clf.clasificar_uno("hola")
    enviado = json.dumps(visto)
    assert "id_cliente" not in enviado and "id_pedido" not in enviado


def test_tipo_invalido_agota_reintentos_y_queda_en_otro():
    clf = ClasificadorLLM(lambda m: '{"tipo": "xyz"}', reintentos=2)
    r = clf.clasificar_uno("texto")
    assert r["tipo"] == OTRO and r["valido"] is False and r["intentos"] == 3 and clf.llamadas == 3
