"""IA-R03: incorporación versionada de etiquetas de tipo de caso.

La decisión de diseño que manda aquí: **una etiqueta propuesta por una IA y una
decidida por personas no son el mismo dato, así que no comparten columna.**
`gold.fact_ticket.tipo_caso` se alimenta solo de decisiones humanas; la propuesta
vive en `tipo_caso_propuesto`. De ese modo publicar una etiqueta sin revisar como
si estuviera validada no depende de que alguien recuerde la convención: no hay
ningún camino en el código que lo permita.

Lo que valida una importación antes de aceptarla:

- **taxonomía**: el tipo tiene que existir en el catálogo; nada de etiquetas nuevas
  coladas por el archivo;
- **procedencia**: `REVISADA` exige `origen='humano'` y los dos anotadores, la
  decisión final y el motivo. Una salida de IA no puede entrar como revisada;
- **unicidad**: el mismo texto dos veces en el mismo lote es ambiguo y se rechaza;
- **versión**: cada importación es un lote con nombre. Reimportar el mismo lote no
  cambia nada; un lote nuevo deja al anterior en la tabla como historia.

La asociación con los tickets va por hash del texto normalizado, no por `id_ticket`:
las 34 descripciones distintas se repiten entre miles de tickets, y etiquetar el
texto una vez es lo que evita contradicciones entre dos tickets que dicen lo mismo.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

# Mismo juego de caracteres que usa la normalización de canal en la versión Spark,
# para que ambos motores produzcan el mismo hash sobre el mismo texto.
ACENTOS = str.maketrans('ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')

ESTADOS = ('PROPUESTA', 'REVISADA')
ORIGEN_HUMANO = 'humano'

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ticket_clasificacion (
    texto_hash   VARCHAR   NOT NULL,
    version      VARCHAR   NOT NULL,
    tipo         VARCHAR   NOT NULL,
    estado       VARCHAR   NOT NULL,   -- PROPUESTA | REVISADA
    origen       VARCHAR   NOT NULL,   -- reglas | llm:<modelo> | humano
    anotadores   VARCHAR,
    motivo       VARCHAR,
    particion    VARCHAR,              -- desarrollo | evaluacion
    confianza    DOUBLE,
    importado_en TIMESTAMP NOT NULL,
    PRIMARY KEY (texto_hash, version)
);

-- Etiqueta vigente por texto: la última importada de cada estado, por separado.
-- Mantener las dos es lo que permite medir a la IA contra la decisión humana sin
-- que una sustituya a la otra.
CREATE OR REPLACE VIEW v_etiqueta_vigente AS
WITH ordenadas AS (
    SELECT *, row_number() OVER (PARTITION BY texto_hash, estado
                                 ORDER BY importado_en DESC, version DESC) AS n
    FROM ticket_clasificacion
)
SELECT texto_hash,
       max(CASE WHEN estado = 'REVISADA'  THEN tipo    END) AS tipo_revisado,
       max(CASE WHEN estado = 'REVISADA'  THEN version END) AS version_revisada,
       max(CASE WHEN estado = 'PROPUESTA' THEN tipo    END) AS tipo_propuesto,
       max(CASE WHEN estado = 'PROPUESTA' THEN version END) AS version_propuesta
FROM ordenadas WHERE n = 1 GROUP BY texto_hash;
"""


class ErrorEtiquetas(ValueError):
    pass


def normalizar_texto(texto) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados.

    Es lo que hace comparable «El equipo no enciende » con «el equipo no enciende»,
    que en la fuente aparecen las dos formas.

    Contrapartida aceptada: la `ñ` se pliega a `n` igual que las tildes, así que
    «año» y «ano» colisionarían. Se asume porque aquí los dos textos vienen de la
    misma fuente y lo que varía es cómo se escribió, no qué dice; si algún día hay
    que distinguirlos, el cambio obliga a reimportar los lotes (el hash cambia).
    """
    return ' '.join(str(texto).translate(ACENTOS).lower().split())


def hash_texto(texto) -> str:
    return hashlib.sha256(normalizar_texto(texto).encode('utf-8')).hexdigest()


def _catalogo() -> set[str]:
    """Catálogo de tipos. Se importa aquí dentro para no atar el ETL a `tickets_ia`."""
    from tickets_ia.taxonomia import ETIQUETAS
    return set(ETIQUETAS)


def leer_revision(path) -> list[dict]:
    """Lee la plantilla de revisión humana (`scripts/revision_etiquetas.py plantilla`).

    Solo devuelve filas con decisión final: una fila a medio llenar no es una
    decisión, y dejarla pasar como tal es justo lo que este flujo debe impedir.
    """
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        filas = list(csv.DictReader(f))
    salida, incompletas = [], 0
    for fila in filas:
        decision = (fila.get('decision_final') or '').strip()
        if not decision:
            incompletas += 1
            continue
        anotadores = [(fila.get(k) or '').strip() for k in ('anotador_1', 'anotador_2')]
        salida.append({
            'texto': fila['descripcion'],
            'tipo': decision,
            'estado': 'REVISADA',
            'origen': ORIGEN_HUMANO,
            'anotadores': ' | '.join(a for a in anotadores if a),
            'motivo': (fila.get('motivo') or '').strip(),
            'particion': (fila.get('particion') or '').strip() or None,
            'confianza': None,
            'anotadores_crudos': anotadores,
        })
    if salida:
        salida[0]['_incompletas'] = incompletas
    return salida


def validar(filas: list[dict]) -> list[dict]:
    """Comprueba taxonomía, procedencia y unicidad. Devuelve las filas con su hash."""
    catalogo = _catalogo()
    vistos: dict[str, str] = {}
    preparadas = []
    for fila in filas:
        tipo, estado = fila['tipo'], fila['estado']
        if tipo not in catalogo:
            raise ErrorEtiquetas(f'Tipo fuera del catálogo: {tipo!r}')
        if estado not in ESTADOS:
            raise ErrorEtiquetas(f'Estado inválido: {estado!r}')
        if estado == 'REVISADA':
            # Una salida de modelo no puede entrar como decisión humana.
            if fila.get('origen') != ORIGEN_HUMANO:
                raise ErrorEtiquetas(
                    f'Etiqueta REVISADA con origen {fila.get("origen")!r}: '
                    'solo una decisión humana puede importarse como revisada')
            anotadores = fila.get('anotadores_crudos') or [
                a for a in (fila.get('anotadores') or '').split('|') if a.strip()]
            if len([a for a in anotadores if a and a.strip()]) < 2:
                raise ErrorEtiquetas(f'Etiqueta REVISADA sin los dos anotadores: {fila["texto"][:40]!r}')
            if not (fila.get('motivo') or '').strip():
                raise ErrorEtiquetas(f'Etiqueta REVISADA sin motivo: {fila["texto"][:40]!r}')
        h = hash_texto(fila['texto'])
        if h in vistos and vistos[h] != tipo:
            raise ErrorEtiquetas(f'El mismo texto llega con dos tipos distintos: {fila["texto"][:40]!r}')
        vistos[h] = tipo
        preparadas.append({**fila, 'texto_hash': h})
    # Un texto repetido con el mismo tipo es redundante, no ambiguo: se deduplica.
    unicas, hechos = [], set()
    for fila in preparadas:
        if fila['texto_hash'] not in hechos:
            hechos.add(fila['texto_hash'])
            unicas.append(fila)
    return unicas


def importar(con, filas: list[dict], version: str) -> dict:
    """Importa un lote. Reimportar el mismo `version` deja la tabla igual.

    No borra lotes anteriores: la historia de cómo se etiquetó es parte de la
    evidencia, y sin ella no se puede explicar por qué un indicador cambió.
    """
    if not version or not str(version).strip():
        raise ErrorEtiquetas('La importación necesita un nombre de versión')
    con.execute(ESQUEMA)
    filas = validar(filas)
    ahora = datetime.now()
    con.execute('DELETE FROM ticket_clasificacion WHERE version = ?', [version])
    for fila in filas:
        con.execute(
            'INSERT INTO ticket_clasificacion VALUES (?,?,?,?,?,?,?,?,?,?)',
            [fila['texto_hash'], version, fila['tipo'], fila['estado'], fila['origen'],
             fila.get('anotadores'), fila.get('motivo'), fila.get('particion'),
             fila.get('confianza'), ahora])

    conocidos = {h for (h,) in con.execute(
        'SELECT DISTINCT texto_hash FROM silver_tickets').fetchall()} if _existe(
            con, 'silver_tickets') else set()
    huerfanas = [f['texto_hash'] for f in filas if conocidos and f['texto_hash'] not in conocidos]
    return {
        'version': version,
        'importadas': len(filas),
        'estado': filas[0]['estado'] if filas else None,
        # Etiquetas cuyo texto no aparece en ningún ticket cargado: no es un error
        # (puede ser una muestra reservada), pero callarlo escondería un desajuste.
        'sin_ticket_asociado': len(huerfanas),
        'tickets_cubiertos': _cobertura(con) if _existe(con, 'silver_tickets') else None,
    }


def _existe(con, tabla: str) -> bool:
    return bool(con.execute(
        'SELECT count(*) FROM information_schema.tables WHERE table_name = ?', [tabla]).fetchone()[0])


def _cobertura(con) -> dict:
    """Cuántos tickets quedan con decisión humana y cuántos solo con propuesta."""
    fila = con.execute("""
        SELECT count(*),
               count(*) FILTER (WHERE e.tipo_revisado IS NOT NULL),
               count(*) FILTER (WHERE e.tipo_revisado IS NULL AND e.tipo_propuesto IS NOT NULL)
        FROM silver_tickets t LEFT JOIN v_etiqueta_vigente e ON e.texto_hash = t.texto_hash
    """).fetchone()
    return {'tickets': fila[0], 'con_decision_humana': fila[1], 'solo_propuesta': fila[2]}


def desde_clasificador(textos_y_tipos, origen: str, confianzas=None) -> list[dict]:
    """Convierte la salida de un clasificador (reglas o LLM) en filas PROPUESTA.

    No acepta `estado`: por construcción, lo que sale de un clasificador es una
    propuesta. Para que sea una decisión tiene que pasar por la revisión humana.
    """
    if origen == ORIGEN_HUMANO:
        raise ErrorEtiquetas("Un clasificador no puede declarar origen 'humano'")
    confianzas = confianzas or {}
    return [{'texto': texto, 'tipo': tipo, 'estado': 'PROPUESTA', 'origen': origen,
             'anotadores': None, 'motivo': None, 'particion': None,
             'confianza': confianzas.get(texto)}
            for texto, tipo in textos_y_tipos]
