"""IA-R01: la impresión de los entregables HTML no se degrada en silencio.

Dos niveles, a propósito:

- Sobre los PDF ya exportados y versionados no hace falta navegador: se lee cada
  página y se comprueba que ninguna quedó vacía ni con una línea suelta. Esto
  corre siempre, también en CI.
- Con Chrome disponible se vuelve a auditar el HTML, pero solo se exige lo que no
  depende de las fuentes instaladas: que cada bloque corto declare que no se
  parte y que nada se salga del ancho de página. Las alturas sí dependen de la
  tipografía del sistema, así que no se convierten en condición de fallo.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from qa_impresion import (  # noqa: E402
    DOCUMENTOS, MINIMO_TEXTO_PAGINA, area_imprimible, buscar_chrome, revisar, texto_por_pagina)

PDFS = [ROOT / 'docs/evidencia/impresion/presentacion_entrega.pdf',
        ROOT / 'docs/evidencia/impresion/presentacion_resolucion_prueba.pdf',
        ROOT / 'docs/04_arquitectura.pdf']


@pytest.mark.parametrize('pdf', PDFS, ids=lambda p: p.name)
def test_ninguna_pagina_del_pdf_queda_vacia_ni_con_una_linea(pdf):
    paginas = texto_por_pagina(pdf)
    assert paginas, f'{pdf.name}: no se pudo leer ninguna página'
    escasas = [(i, len(t), t[:60]) for i, t in enumerate(paginas, 1) if len(t) < MINIMO_TEXTO_PAGINA]
    assert not escasas, f'{pdf.name}: páginas sin contenido suficiente {escasas}'


def test_area_imprimible_sale_de_la_regla_page():
    assert area_imprimible('@page{size:A4 landscape;margin:12mm}') == (1032, 703)
    assert area_imprimible('@page { size: A4; margin: 12mm 13mm; }') == (695, 1032)
    assert area_imprimible('sin regla') == (703, 1032)        # A4 vertical, 12mm por defecto


@pytest.mark.skipif(buscar_chrome() is None, reason='Chrome no disponible para auditar impresión')
def test_la_maquetacion_de_impresion_protege_los_bloques(tmp_path):
    informe = revisar(DOCUMENTOS, pdf=False, paginas=False, destino=tmp_path)
    # Font-independientes: declaración de corte y ancho de página.
    criticos = [p for d in informe['documentos'] for p in d['problemas']
                if p['tipo'] in ('bloque_sin_break_inside_avoid', 'desborde_horizontal',
                                 'contenido_recortado_en_x', 'bloque_largo_no_puede_cortarse',
                                 'tabla_larga_sin_encabezado_repetido')]
    assert not criticos, criticos[:10]
    assert all(d['capitulos'] >= 2 for d in informe['documentos'])
