"""Clasificador con un LLM de API compatible con OpenAI (DeepSeek por defecto).

La función que llama a la API se inyecta (`llamar`), así la lógica (prompt, validación, reintentos,
caché) se prueba sin red. Solo se envía el TEXTO de la descripción: nunca ids de cliente o pedido.
"""
from __future__ import annotations

import json
import math
import time
import hashlib
import os
from pathlib import Path

from .taxonomia import ETIQUETAS, OTRO, SISTEMA

MODELO_POR_DEFECTO = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"
ENV_LOCAL = Path(__file__).resolve().parents[3] / ".env.local"  # raíz del repositorio; ignorado por git


def cargar_env_local(ruta: Path = ENV_LOCAL) -> None:
    """Carga pares CLAVE=valor de .env.local en el entorno. No sobrescribe lo que ya esté definido:
    una variable exportada en la terminal tiene prioridad sobre el archivo."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def crear_llamada_deepseek(modelo: str = MODELO_POR_DEFECTO):
    """Devuelve llamar(mensajes) -> texto. La clave sale de DEEPSEEK_API_KEY (del entorno o de
    .env.local), nunca del código. El modo 'thinking' se desactiva: con él, cada llamada genera
    miles de tokens de razonamiento y el costo se multiplica, sin aportar a una clasificación de
    una sola etiqueta."""
    from openai import OpenAI  # dependencia opcional (requirements-ia.txt)
    cargar_env_local()
    clave = os.environ.get("DEEPSEEK_API_KEY")
    if not clave:
        raise RuntimeError("Falta DEEPSEEK_API_KEY: defínela en el entorno o en .env.local (raíz del repositorio)")
    cliente = OpenAI(api_key=clave, base_url=BASE_URL, timeout=20.0, max_retries=0)

    def llamar(mensajes):
        r = cliente.chat.completions.create(
            model=modelo, messages=mensajes, temperature=0, max_tokens=200,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}})
        # El consumo se deja en el propio callable para no cambiar su firma: la
        # inyección de `llamar` es lo que permite probar sin red.
        uso = getattr(r, "usage", None)
        llamar.ultimo_uso = {
            "tokens_entrada": getattr(uso, "prompt_tokens", None),
            "tokens_salida": getattr(uso, "completion_tokens", None),
        } if uso else None
        return r.choices[0].message.content or ""
    llamar.ultimo_uso = None
    return llamar


def interpretar(respuesta: str):
    """(tipo, confianza, valido). Un tipo fuera del catálogo se convierte en 'otro' y se marca inválido."""
    try:
        d = json.loads(respuesta)
        if not isinstance(d, dict) or not isinstance(d.get("tipo"), str):
            return OTRO, None, False
        tipo = d["tipo"].strip()
        conf = d.get("confianza")
        if conf is not None and (isinstance(conf, bool) or not isinstance(conf, (float, int))
                                 or not math.isfinite(conf) or not 0 <= conf <= 1):
            return OTRO, None, False
        conf = float(conf) if conf is not None else None
    except (ValueError, TypeError, AttributeError):
        return OTRO, None, False
    if tipo not in ETIQUETAS:
        return OTRO, conf, False
    return tipo, conf, True


class ClasificadorLLM:
    def __init__(self, llamar, reintentos: int = 2, *, max_llamadas: int = 1000,
                 dormir=time.sleep, modelo: str = MODELO_POR_DEFECTO):
        if reintentos < 0 or max_llamadas < 1:
            raise ValueError('Presupuesto de intentos inválido')
        self.llamar, self.reintentos = llamar, reintentos
        self.max_llamadas, self.dormir, self.modelo = max_llamadas, dormir, modelo
        self.cache: dict[str, dict] = {}
        self.llamadas = 0
        # Una medición por llamada a la API (no por texto): los textos repetidos salen
        # de la caché y no cuestan nada, y mezclarlos falsearía la latencia media.
        self.telemetria: list[dict] = []
        self.prompt_version = hashlib.sha256(SISTEMA.encode()).hexdigest()[:16]

    def clasificar_uno(self, texto: str) -> dict:
        if texto in self.cache:
            return dict(self.cache[texto])
        mensajes = [{"role": "system", "content": SISTEMA},
                    {"role": "user", "content": f"Texto del cliente: {texto}"}]
        resultado = dict(tipo=OTRO, confianza=None, valido=False, intentos=0,
                         modelo=self.modelo, prompt_version=self.prompt_version,
                         revision_humana=True, error=None)
        for intento in range(1, self.reintentos + 2):
            if self.llamadas >= self.max_llamadas:
                resultado['error'] = 'PRESUPUESTO_AGOTADO'
                break
            self.llamadas += 1
            resultado['intentos'] = intento
            inicio = time.perf_counter()
            try:
                respuesta = self.llamar(mensajes)
            except Exception as exc:
                self._medir(inicio, False)
                status = getattr(exc, 'status_code', None)
                temporal = isinstance(exc, (TimeoutError, ConnectionError)) or status in (408, 429, 500, 502, 503, 504)
                temporal = temporal or type(exc).__name__ in ('APITimeoutError', 'APIConnectionError')
                # No guardar str(exc): puede incluir texto, URLs o información de autenticación.
                resultado['error'] = 'TRANSPORTE_TRANSITORIO' if temporal else 'ERROR_PERMANENTE'
                if not temporal:
                    break
            else:
                self._medir(inicio, True)
                tipo, conf, ok = interpretar(respuesta)
                resultado.update(tipo=tipo, confianza=conf, valido=ok,
                                 error=None if ok else 'RESPUESTA_INVALIDA')
                if ok:
                    self.cache[texto] = dict(resultado)
                    break
            if intento <= self.reintentos and self.llamadas < self.max_llamadas:
                self.dormir(min(0.25 * 2 ** (intento - 1), 2))
        return resultado

    def _medir(self, inicio: float, exito: bool) -> None:
        """Registra la llamada aunque haya fallado: una corrida con muchos reintentos
        cuesta tiempo y tokens igual, y ocultarlo subestimaría el costo real."""
        uso = getattr(self.llamar, 'ultimo_uso', None) or {}
        self.telemetria.append({
            'latencia_s': time.perf_counter() - inicio,
            'exito': exito,
            'tokens_entrada': uso.get('tokens_entrada'),
            'tokens_salida': uso.get('tokens_salida'),
        })

    def clasificar(self, textos):
        return [self.clasificar_uno(t) for t in textos]
