"""IA-R01: auditoría de impresión página a página de los HTML entregables.

Qué hace, y por qué así: revisar "a ojo" un PDF no es reproducible ni deja
evidencia. Este script fuerza las reglas `@media print` sobre pantalla, alinea
cada capítulo al inicio de página (lo que hace `page-break-before: always`) y
mide la maquetación dentro del área imprimible que declara `@page`.

Solo comprueba lo que puede afirmar con exactitud, sin simular el paginador:

- un bloque corto más alto que la página se corta sí o sí, haga lo que haga el
  motor de impresión;
- un bloque corto sin `break-inside: avoid` queda a merced del salto;
- un bloque largo (código, tabla) con `break-inside: avoid` no cabe y se corta mal;
- una tabla de más de una página sin `thead` repetido pierde el encabezado;
- desbordes horizontales y contenido recortado en X.

Dónde cae exactamente cada corte es cosa del paginador del navegador: eso se
certifica con `--paginas`, que exporta una imagen por página para revisarlas.
El conteo de páginas estimado se contrasta contra el PDF real con `--pdf`.

Uso (desde la raíz del repositorio):
  python scripts/qa_impresion.py                  # audita y escribe la evidencia
  python scripts/qa_impresion.py --pdf            # además exporta los PDF
  python scripts/qa_impresion.py --paginas        # además una PNG por página
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALIDA = ROOT / 'docs/evidencia/impresion'
DOCUMENTOS = ['docs/presentacion_entrega.html', 'docs/presentacion_resolucion_prueba.html',
              'docs/04_arquitectura.html']
PX_POR_MM = 96 / 25.4
HOJAS = {'a4': (210, 297)}

# Bloques cortos: deben caber enteros en una página y declarar que no se parten.
SELECTOR_ATOMICOS = ('.card,.panel,.gap,.flow-node,.callout,.takeaway,.request,.answer-state,'
                     '.score-row,.quality-bar,.roadmap article,blockquote,figure,svg,li,tr')
# Bloques largos legítimos (listados de código, tablas): pueden ocupar varias páginas,
# pero tienen que poder cortarse y, si son tablas, repetir el encabezado.
SELECTOR_DIVISIBLES = 'pre,table,.table-wrap,.code-detail'
# Una página con menos texto que esto no es una página: es una línea que se quedó sola
# al otro lado de un salto. Las portadas de capítulo llevan título y bajada, y superan
# este umbral con holgura.
MINIMO_TEXTO_PAGINA = 120
CANDIDATOS_CHROME = [
    os.environ.get('CHROME_BIN'),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
]


def buscar_chrome() -> str | None:
    for ruta in CANDIDATOS_CHROME:
        if ruta and Path(ruta).exists():
            return str(ruta)
    for nombre in ('google-chrome', 'chromium', 'chrome'):
        if encontrado := shutil.which(nombre):
            return encontrado
    return None


def area_imprimible(html: str) -> tuple[int, int]:
    """Área de contenido en px CSS a partir de `@page`. Sin `@page`, A4 vertical con 12mm."""
    bloque = re.search(r'@page\s*\{([^}]*)\}', html)
    texto = bloque.group(1).lower() if bloque else ''
    ancho_mm, alto_mm = HOJAS['a4']
    if 'landscape' in texto:
        ancho_mm, alto_mm = alto_mm, ancho_mm
    margenes = [float(v) for v in re.findall(r'(\d+(?:\.\d+)?)mm', texto.split('margin', 1)[1])] \
        if 'margin' in texto else [12.0]
    vertical, horizontal = (margenes + margenes)[:2] if len(margenes) > 1 else (margenes[0], margenes[0])
    return (round((ancho_mm - 2 * horizontal) * PX_POR_MM), round((alto_mm - 2 * vertical) * PX_POR_MM))


AUDITORIA_JS = '''
<script id="qa-impresion-script">
(function(){
  var ALTO = __ALTO__, ANCHO = __ANCHO__, PAGINA = __PAGINA__;
  function medir(){
    var capitulos = Array.prototype.slice.call(document.querySelectorAll('__CAPITULO__'));
    // page-break-before: always -> cada capítulo arranca en el borde de una página.
    // `.chapter:first-child` lo evita, así que ese solo se alinea si lleva algo delante.
    capitulos.forEach(function(ch, i){
      if (i === 0 && ch.matches(':first-child')) return;
      var top = ch.getBoundingClientRect().top + window.scrollY;
      var resto = top % ALTO;
      if (resto > 0.5) {
        var previo = parseFloat(getComputedStyle(ch).marginTop) || 0;
        ch.style.marginTop = (previo + (ALTO - resto)) + 'px';
      }
    });
    var problemas = [], detalle = [];
    function nombrar(el){
      return el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
             ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
    }
    function evitaCorte(el){
      var s = getComputedStyle(el);
      return (s.breakInside || s.pageBreakInside || '').indexOf('avoid') >= 0;
    }
    // Inicio de cada sección ya alineado; sirve para situar los hallazgos y medir alturas.
    var inicios = capitulos.map(function(ch){ return ch.getBoundingClientRect().top + window.scrollY; });
    var finDoc = document.documentElement.getBoundingClientRect().height;
    capitulos.forEach(function(ch, i){
      var base = inicios[i];
      var alto = (i + 1 < inicios.length ? inicios[i + 1] : finDoc) - base;
      detalle.push({orden: i + 1, id: ch.id || null, alto_px: Math.round(alto),
                    paginas: Math.max(1, Math.ceil((alto - 1) / ALTO)),
                    pagina_inicial: Math.round(base / ALTO) + 1});
    });
    function seccion(top){
      var n = 0;
      for (var k = 0; k < inicios.length; k++) { if (inicios[k] <= top + 1) n = k + 1; }
      return n;
    }
    function referencia(el, e){
      var top = e.top + window.scrollY, n = seccion(top);
      return {capitulo: n, capitulo_id: n ? (capitulos[n - 1].id || null) : null,
              bloque: nombrar(el), alto_px: Math.round(e.height),
              pagina: Math.floor(top / ALTO) + 1};
    }
    // Se recorre el documento entero: hay entregables planos (sin capítulos) donde los
    // bloques son hermanos del salto de página, no descendientes suyos.
    Array.prototype.slice.call(document.body.querySelectorAll('__ATOMICOS__')).forEach(function(el){
      var e = el.getBoundingClientRect();
      if (e.height < 2 || e.width < 2) return;
      var ref = referencia(el, e);
      // Más alto que la página: ninguna regla de salto evita que se corte.
      if (e.height > ALTO) problemas.push(Object.assign({tipo: 'bloque_corto_mas_alto_que_pagina'}, ref));
      // Sin protección declarada, el salto puede caer en medio del bloque.
      else if (!evitaCorte(el)) problemas.push(Object.assign({tipo: 'bloque_sin_break_inside_avoid'}, ref));
    });

    Array.prototype.slice.call(document.body.querySelectorAll('__DIVISIBLES__')).forEach(function(el){
      var e = el.getBoundingClientRect();
      if (e.height < 2 || e.width < 2) return;
      if (e.height <= ALTO) return;                         // cabe en una página: nada que exigir
      var ref = referencia(el, e);
      if (evitaCorte(el)) problemas.push(Object.assign({tipo: 'bloque_largo_no_puede_cortarse'}, ref));
      var cabecera = el.tagName === 'TABLE' ? el.querySelector('thead') : null;
      if (el.tagName === 'TABLE' && (!cabecera ||
          getComputedStyle(cabecera).display !== 'table-header-group')) {
        problemas.push(Object.assign({tipo: 'tabla_larga_sin_encabezado_repetido'}, ref));
      }
    });

    // Desbordes horizontales: exactos, no dependen del paginador.
    Array.prototype.slice.call(document.body.querySelectorAll('*')).forEach(function(el){
      var e = el.getBoundingClientRect();
      if (e.height < 2 || e.width < 2) return;
      var ref = referencia(el, e);
      if (e.right > ANCHO + 1 || e.left < -1) {
        problemas.push(Object.assign({tipo: 'desborde_horizontal',
                       izquierda_px: Math.round(e.left), derecha_px: Math.round(e.right)}, ref));
      } else if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
                 getComputedStyle(el).overflowX === 'hidden') {
        problemas.push(Object.assign({tipo: 'contenido_recortado_en_x',
                       scroll_px: el.scrollWidth, visible_px: el.clientWidth}, ref));
      }
    });
    var total = Math.ceil((document.documentElement.getBoundingClientRect().height - 1) / ALTO);
    var salida = {area_px: [ANCHO, ALTO], capitulos: detalle.length,
                  paginas_estimadas: Math.max(total, 1), problemas: problemas, capitulo_detalle: detalle};
    if (PAGINA !== null) {
      document.documentElement.style.cssText += ';overflow:hidden;height:' + ALTO + 'px;';
      document.body.style.cssText += ';transform:translateY(' + (-(PAGINA - 1) * ALTO)
                                     + 'px);margin:0;overflow:hidden;';
    }
    var pre = document.createElement('script');
    pre.type = 'application/json';
    pre.id = 'qa-impresion-resultado';
    pre.textContent = JSON.stringify(salida);
    document.body.appendChild(pre);
  }
  function arrancar(){
    // La página escucha `beforeprint` para abrir los <details>: sin disparar el evento se
    // medirían plegados y el documento saldría mucho más corto que el PDF real.
    try { window.dispatchEvent(new Event('beforeprint')); } catch (e) {}
    setTimeout(medir, 400);
  }
  if (document.readyState === 'complete') { setTimeout(arrancar, 400); }
  else { window.addEventListener('load', function(){ setTimeout(arrancar, 400); }); }
})();
</script>
'''


def _preparar(html: str, ancho: int, alto: int, capitulo_sel: str, pagina: int | None) -> str:
    """Copia del documento con las reglas de impresión activas en pantalla y el script de medición."""
    # `@media print` -> `@media all`: así el navegador aplica en pantalla exactamente las reglas
    # que usaría al imprimir, y se pueden medir con getBoundingClientRect.
    texto = re.sub(r'@media\s+print\s*\{', '@media all{', html)
    script = (AUDITORIA_JS.replace('__ALTO__', str(alto)).replace('__ANCHO__', str(ancho))
              .replace('__CAPITULO__', capitulo_sel)
              .replace('__ATOMICOS__', SELECTOR_ATOMICOS)
              .replace('__DIVISIBLES__', SELECTOR_DIVISIBLES)
              .replace('__PAGINA__', 'null' if pagina is None else str(pagina)))
    return texto.replace('</body>', script + '</body>') if '</body>' in texto else texto + script


def _chrome(binario: str, url: str, ancho: int, alto: int, *extra: str) -> str:
    orden = [binario, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
             '--disable-extensions', '--hide-scrollbars', '--force-device-scale-factor=1',
             '--run-all-compositor-stages-before-draw', '--virtual-time-budget=9000',
             f'--window-size={ancho},{alto}', *extra, url]
    r = subprocess.run(orden, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    return (r.stdout or '') + (r.stderr or '')


def auditar(documento: str, binario: str, pdf: bool = False, paginas: bool = False,
            destino: Path = SALIDA) -> dict:
    ruta = ROOT / documento
    destino = Path(destino).resolve()
    html = ruta.read_text(encoding='utf-8')
    ancho, alto = area_imprimible(html)
    # En arquitectura el salto de página lo marca `.pg`; en las presentaciones, cada `.chapter`.
    capitulo_sel = '.chapter' if '"chapter"' in html or 'class="chapter' in html else '.pg,body>h1'
    destino.mkdir(parents=True, exist_ok=True)
    nombre = Path(documento).stem

    with tempfile.TemporaryDirectory(prefix='andina-qa-impresion-') as tmp:
        tmp = Path(tmp)
        # La copia va al lado del original para que resuelva las rutas relativas igual.
        copia = ruta.with_name(f'.qa_impresion_{nombre}.html')
        copia.write_text(_preparar(html, ancho, alto, capitulo_sel, None), encoding='utf-8')
        try:
            volcado = _chrome(binario, copia.as_uri(), ancho, alto, '--dump-dom',
                              f'--user-data-dir={tmp / "perfil"}')
        finally:
            copia.unlink(missing_ok=True)
        encontrado = re.search(
            r'<script type="application/json" id="qa-impresion-resultado">(.*?)</script>', volcado, re.S)
        if not encontrado:
            raise RuntimeError(f'{documento}: la medición no se ejecutó en el navegador')
        resultado = json.loads(encontrado.group(1))
        resultado['documento'] = documento

        if pdf:
            salida_pdf = destino / f'{nombre}.pdf'
            _chrome(binario, ruta.as_uri(), ancho, alto, '--no-pdf-header-footer',
                    f'--print-to-pdf={salida_pdf}', f'--user-data-dir={tmp / "perfil-pdf"}')
            resultado['pdf'] = _relativo(salida_pdf)
            resultado['paginas_pdf'] = _paginas_pdf(salida_pdf)
            # Revisión página a página sobre el PDF ya impreso: aquí no hay modelo,
            # es lo que el lector va a recibir.
            paginas_texto = texto_por_pagina(salida_pdf)
            resultado['inventario_paginas'] = [
                {'pagina': i, 'caracteres': len(t), 'inicio': t[:90]}
                for i, t in enumerate(paginas_texto, 1)]
            resultado['problemas'] += [
                {'tipo': 'pagina_sin_texto' if not t.strip() else 'pagina_con_una_linea_suelta',
                 'pagina': i, 'caracteres': len(t), 'inicio': t[:90]}
                for i, t in enumerate(paginas_texto, 1) if len(t) < MINIMO_TEXTO_PAGINA]

        if paginas:
            carpeta = destino / f'paginas_{nombre}'
            carpeta.mkdir(parents=True, exist_ok=True)
            for n in range(1, resultado['paginas_estimadas'] + 1):
                copia.write_text(_preparar(html, ancho, alto, capitulo_sel, n), encoding='utf-8')
                try:
                    _chrome(binario, copia.as_uri(), ancho, alto,
                            f'--screenshot={carpeta / f"pagina_{n:02d}.png"}',
                            f'--user-data-dir={tmp / f"perfil-{n}"}')
                finally:
                    copia.unlink(missing_ok=True)
            resultado['imagenes'] = _relativo(carpeta)
    return resultado


def _relativo(ruta: Path) -> str:
    """Ruta relativa al repositorio cuando cae dentro; absoluta si el destino es externo."""
    try:
        return str(ruta.resolve().relative_to(ROOT))
    except ValueError:
        return str(ruta.resolve())


def _paginas_pdf(ruta: Path) -> int:
    """Número de páginas leyendo el árbol del PDF, sin dependencias externas."""
    datos = ruta.read_bytes()
    cuentas = [int(x) for x in re.findall(rb'/Count\s+(\d+)', datos)]
    return max(cuentas) if cuentas else len(re.findall(rb'/Type\s*/Page[^s]', datos))


# ---------------------------------------------------------------------------
# Lectura del PDF ya impreso: es la única fuente que dice, sin aproximaciones,
# qué quedó en cada página. Se hace a mano para no añadir dependencias.
# ---------------------------------------------------------------------------
def _objetos(datos: bytes) -> dict[int, bytes]:
    return {int(m.group(1)): m.group(2)
            for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', datos, re.S)}


def _flujo(cuerpo: bytes) -> bytes:
    m = re.search(rb'stream\r?\n(.*?)\r?\nendstream', cuerpo, re.S)
    if not m:
        return b''
    if b'/FlateDecode' not in cuerpo:
        return m.group(1)
    try:
        import zlib
        return zlib.decompress(m.group(1))
    except Exception:
        return b''


def _tabla_unicode(texto: bytes) -> dict[int, str]:
    """CMap /ToUnicode -> código de glifo a carácter."""
    tabla: dict[int, str] = {}
    for m in re.finditer(rb'beginbfchar(.*?)endbfchar', texto, re.S):
        for a, b in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', m.group(1)):
            tabla[int(a, 16)] = bytes.fromhex(b.decode()).decode('utf-16-be', 'replace')
    for m in re.finditer(rb'beginbfrange(.*?)endbfrange', texto, re.S):
        for a, b, c in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', m.group(1)):
            lo, hi, destino = int(a, 16), int(b, 16), int(c, 16)
            for k in range(lo, hi + 1):
                tabla[k] = chr(destino + k - lo)
    return tabla


def texto_por_pagina(ruta: Path) -> list[str]:
    """Texto de cada página del PDF, en orden. Las fuentes de Chrome son Type0 con
    /ToUnicode, así que los códigos de glifo se traducen con esa tabla."""
    objetos = _objetos(ruta.read_bytes())
    paginas = [n for n in sorted(objetos) if re.search(rb'/Type\s*/Page[^s]', objetos[n])]
    salida = []
    for n in paginas:
        cuerpo = objetos[n]
        fuentes: dict[str, dict[int, str]] = {}
        recursos = re.search(rb'/Font\s*<<(.*?)>>', cuerpo, re.S)
        if recursos:
            for nombre, ref in re.findall(rb'/(\w+)\s+(\d+)\s+0\s+R', recursos.group(1)):
                fuente = objetos.get(int(ref), b'')
                unicode_ref = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', fuente)
                if not unicode_ref:
                    hijo = re.search(rb'/DescendantFonts\s*\[\s*(\d+)\s+0\s+R', fuente)
                    if hijo:
                        unicode_ref = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R',
                                                objetos.get(int(hijo.group(1)), b''))
                fuentes[nombre.decode()] = (_tabla_unicode(_flujo(objetos[int(unicode_ref.group(1))]))
                                            if unicode_ref else {})
        contenido = re.search(rb'/Contents\s+(\d+)\s+0\s+R', cuerpo)
        flujo = _flujo(objetos[int(contenido.group(1))]) if contenido else b''
        actual: dict[int, str] = {}
        piezas: list[str] = []
        for m in re.finditer(rb'/(\w+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]+)>\s*Tj|\[(.*?)\]\s*TJ', flujo, re.S):
            if m.group(1):
                actual = fuentes.get(m.group(1).decode(), {})
                continue
            codigos = [m.group(2)] if m.group(2) else re.findall(rb'<([0-9A-Fa-f]+)>', m.group(3) or b'')
            for bloque in codigos:
                s = bloque.decode()
                piezas.append(''.join(actual.get(int(s[i:i + 4], 16), '') for i in range(0, len(s) - 3, 4)))
        salida.append(' '.join(' '.join(piezas).split()))
    return salida


def revisar(documentos=DOCUMENTOS, pdf=False, paginas=False, destino=SALIDA) -> dict:
    binario = buscar_chrome()
    if not binario:
        raise RuntimeError('No se encontró Chrome/Chromium; definir CHROME_BIN para auditar impresión')
    informes = [auditar(d, binario, pdf, paginas, destino) for d in documentos]
    problemas = [p for i in informes for p in i['problemas']]
    resumen = {
        'navegador': 'Chrome headless local',
        'metodo': 'reglas @media print aplicadas en pantalla; capítulos alineados al borde de página',
        'alcance': ('comprueba altura de bloque contra página, declaración de break-inside, '
                    'encabezado repetido en tablas largas y desbordes horizontales'),
        'fuera_de_alcance': ('en qué punto exacto cae cada salto lo decide el paginador del '
                             'navegador; eso se certifica con la revisión por imagen (--paginas)'),
        'documentos': informes,
        'problemas_totales': len(problemas),
        'estado': 'SIN_HALLAZGOS' if not problemas else 'CON_HALLAZGOS',
    }
    destino.mkdir(parents=True, exist_ok=True)
    (destino / 'qa_impresion.json').write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
    return resumen


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--pdf', action='store_true', help='exportar también el PDF de cada documento')
    p.add_argument('--paginas', action='store_true', help='exportar una PNG por página para revisión visual')
    p.add_argument('--documento', action='append', help='limitar a un HTML (ruta relativa al repositorio)')
    p.add_argument('--out', type=Path, default=SALIDA)
    a = p.parse_args()
    r = revisar(a.documento or DOCUMENTOS, a.pdf, a.paginas, a.out)
    for d in r['documentos']:
        print(f"{d['documento']}: {d['capitulos']} capítulos, {d['paginas_estimadas']} páginas, "
              f"{len(d['problemas'])} hallazgos" + (f", pdf {d.get('paginas_pdf')} páginas" if 'pdf' in d else ''))
        for q in d['problemas'][:40]:
            print('   ', json.dumps(q, ensure_ascii=False))
    print(f"estado: {r['estado']} ({r['problemas_totales']} hallazgos)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
