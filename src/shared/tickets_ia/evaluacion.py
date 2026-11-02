"""IA-R04: arnés para evaluar un clasificador sobre una muestra reservada.

Qué añade sobre `metricas.evaluar`, y por qué cada cosa:

- **Intervalos de confianza.** Con 150 frases, una exactitud de 0,627 y otra de 0,68
  no son distinguibles. Dar la cifra sin el intervalo invita a leer como mejora lo
  que es ruido muestral. Se usa el intervalo de Wilson, que a diferencia del normal
  no se sale de [0,1] ni se rompe cuando una clase acierta todo o nada.
- **Errores críticos.** No todos los errores cuestan lo mismo: confundir dos tipos de
  queja de producto reparte mal el trabajo; mandar un cobro duplicado a la cola de
  felicitaciones deja a una persona sin su dinero. La exactitud media los trata igual.
- **Fugas.** Una muestra «reservada» que comparte textos con la de desarrollo no mide
  generalización, mide memoria. Se comprueba antes de reportar nada.
- **Costo y latencia.** Decidir si el LLM compensa frente a las reglas exige saber qué
  cuesta y cuánto tarda, no solo si acierta más.

Los grupos de gravedad de abajo son una **propuesta**, no una política acordada:
quién atiende cada cola y qué error es inaceptable lo define negocio (U08/E06).
"""
from __future__ import annotations

import math

from .metricas import evaluar as evaluar_basico
from .reglas import normalizar
from .taxonomia import ETIQUETAS, OTRO

# Agrupaciones por consecuencia del error, no por parecido del texto.
DINERO = frozenset({'cobro_duplicado', 'pago_rechazado_con_cargo', 'reembolso_cancelado',
                    'cupon_no_aplicado'})
DATOS_PERSONALES = frozenset({'eliminar_cuenta', 'actualizar_datos'})
FELICITACIONES = frozenset({'felicitacion_cambio', 'felicitacion_atencion'})

TIPOS_CRITICOS = {
    'dinero_mal_enrutado': (
        'Un caso de dinero se clasifica como algo que no lo es: la persona queda sin '
        'su reclamo económico en la cola correcta.'),
    'derecho_de_datos_perdido': (
        'Una solicitud de eliminación o corrección de datos personales se clasifica como '
        'otra cosa: es una obligación legal, no una preferencia de atención.'),
    'problema_como_felicitacion': (
        'Un problema real se clasifica como felicitación: el caso se cierra como opinión '
        'positiva y nadie lo atiende.'),
}


def intervalo_wilson(exitos: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Intervalo de Wilson al 95 % por defecto. None si no hay observaciones.

    Se prefiere al intervalo normal porque con n pequeño o proporciones cerca de 0 o 1
    aquél devuelve límites fuera de [0,1] y anchura cero cuando se acierta todo.
    """
    if n <= 0:
        return None
    p = exitos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    radio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    return (max(0.0, centro - radio), min(1.0, centro + radio))


def _percentil(valores: list[float], q: float) -> float | None:
    """Percentil por interpolación lineal, sin dependencias externas."""
    if not valores:
        return None
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    pos = q * (len(ordenados) - 1)
    bajo = math.floor(pos)
    alto = math.ceil(pos)
    if bajo == alto:
        return ordenados[int(pos)]
    return ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (pos - bajo)


def fugas(textos_muestra, textos_desarrollo) -> list[int]:
    """Índices de la muestra cuyo texto normalizado ya aparecía en desarrollo.

    Detecta la copia literal y la diferencia de mayúsculas o tildes. **No** detecta
    una paráfrasis: que esto salga vacío no acredita independencia semántica.
    """
    conocidos = {' '.join(normalizar(t).split()) for t in textos_desarrollo}
    return [i for i, t in enumerate(textos_muestra)
            if ' '.join(normalizar(t).split()) in conocidos]


def errores_criticos(textos, reales, predichos) -> list[dict]:
    """Errores cuya consecuencia operativa es distinta de «se repartió mal el trabajo»."""
    encontrados = []
    for i, (texto, real, predicho) in enumerate(zip(textos, reales, predichos)):
        if real == predicho:
            continue
        tipo = None
        if real in DINERO and predicho not in DINERO:
            tipo = 'dinero_mal_enrutado'
        elif real in DATOS_PERSONALES and predicho not in DATOS_PERSONALES:
            tipo = 'derecho_de_datos_perdido'
        elif real not in FELICITACIONES and predicho in FELICITACIONES:
            tipo = 'problema_como_felicitacion'
        if tipo:
            encontrados.append({'indice': i, 'tipo_error': tipo, 'real': real,
                                'predicho': predicho, 'texto': texto})
    return encontrados


def resumen_telemetria(registros, precios: dict | None = None) -> dict:
    """Costo y latencia a partir de lo que registró el clasificador.

    `precios` es opcional y debe venir del proveedor: {'entrada': COP por 1M tokens,
    'salida': ...}. Sin él se informan tokens y se dice que el costo no se calculó;
    inventar una tarifa sería peor que no darla.
    """
    registros = [r for r in (registros or []) if r]
    latencias = [r['latencia_s'] for r in registros if r.get('latencia_s') is not None]
    entrada = sum(r.get('tokens_entrada') or 0 for r in registros)
    salida = sum(r.get('tokens_salida') or 0 for r in registros)
    resumen = {
        'llamadas': len(registros),
        'latencia_s': {'total': round(sum(latencias), 3) if latencias else None,
                       'mediana': round(_percentil(latencias, 0.5), 3) if latencias else None,
                       'p95': round(_percentil(latencias, 0.95), 3) if latencias else None,
                       'maxima': round(max(latencias), 3) if latencias else None},
        'tokens': {'entrada': entrada, 'salida': salida, 'total': entrada + salida},
    }
    if precios and (entrada or salida):
        resumen['costo'] = {
            'moneda': precios.get('moneda', 'no declarada'),
            'total': round(entrada / 1e6 * precios.get('entrada', 0)
                           + salida / 1e6 * precios.get('salida', 0), 4),
            'tarifa_declarada_por_el_usuario': True,
        }
    else:
        resumen['costo'] = {'calculado': False,
                            'motivo': 'No se declararon tarifas; no se inventa un precio'}
    return resumen


def evaluar_reservada(textos, reales, predichos, *, desarrollo=None, telemetria=None,
                      precios=None, etiquetas=None, procedencia='no declarada') -> dict:
    """Informe completo sobre una muestra reservada.

    `procedencia` describe de dónde salió la muestra y quién la etiquetó. Es
    obligatorio declararla: un informe que no dice si los datos son reales o
    sintéticos se acaba citando como si fueran reales.
    """
    if not (len(textos) == len(reales) == len(predichos)):
        raise ValueError('textos, reales y predichos deben tener el mismo tamaño')
    if not textos:
        raise ValueError('La muestra reservada está vacía')
    etiquetas = list(etiquetas or ETIQUETAS)
    desconocidas = sorted({r for r in reales if r not in etiquetas})
    if desconocidas:
        raise ValueError(f'Etiquetas fuera del catálogo en la muestra: {desconocidas}')

    base = evaluar_basico(reales, predichos, etiquetas)
    n = len(reales)
    aciertos = sum(r == p for r, p in zip(reales, predichos))

    por_clase = {}
    for etiqueta, valores in base['por_clase'].items():
        soporte = valores['soporte']
        if not soporte and valores['precision'] is None:
            continue
        tp = base['matriz'].get(etiqueta, {}).get(etiqueta, 0)
        predichos_clase = sum(1 for p in predichos if p == etiqueta)
        por_clase[etiqueta] = {
            **valores,
            'intervalo_recall': intervalo_wilson(tp, soporte),
            'intervalo_precision': intervalo_wilson(tp, predichos_clase),
        }

    criticos = errores_criticos(textos, reales, predichos)
    conteo_criticos = {t: sum(1 for e in criticos if e['tipo_error'] == t) for t in TIPOS_CRITICOS}
    a_otro = sum(1 for r, p in zip(reales, predichos) if p == OTRO and r != OTRO)

    informe = {
        'procedencia_de_la_muestra': procedencia,
        'n': n,
        'exactitud': aciertos / n,
        'intervalo_exactitud': intervalo_wilson(aciertos, n),
        'f1_macro': base['f1_macro'],
        'por_clase': por_clase,
        'matriz_confusion': base['matriz'],
        'errores': [{'texto': t, 'real': r, 'predicho': p}
                    for t, r, p in zip(textos, reales, predichos) if r != p],
        'errores_criticos': {
            'definicion': TIPOS_CRITICOS,
            'estado_de_la_definicion': 'PROPUESTA: pendiente de acuerdo con negocio (U08/E06)',
            'conteo': conteo_criticos,
            'tasa': {t: c / n for t, c in conteo_criticos.items()},
            'casos': criticos,
        },
        'clasificados_como_otro_siendo_un_tipo': a_otro,
        'telemetria': resumen_telemetria(telemetria, precios),
    }

    if desarrollo is not None:
        indices = fugas(textos, desarrollo)
        informe['fugas'] = {
            'indices': indices,
            'cuantas': len(indices),
            'alcance': ('detecta copia literal y diferencias de mayúsculas, tildes o espacios; '
                        'no detecta paráfrasis'),
        }
        informe['muestra_reservada_valida'] = not indices
    else:
        informe['fugas'] = {'comprobado': False,
                            'motivo': 'No se aportó el conjunto de desarrollo'}
        informe['muestra_reservada_valida'] = None
    return informe
