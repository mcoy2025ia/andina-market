"""Clasificador con un LLM de API compatible con OpenAI (DeepSeek por defecto).

La función que llama a la API se inyecta (`llamar`), así la lógica (prompt, validación, reintentos,
caché) se prueba sin red. Solo se envía el TEXTO de la descripción: nunca ids de cliente o pedido.
"""
from __future__ import annotations

import json
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
    cliente = OpenAI(api_key=clave, base_url=BASE_URL)

    def llamar(mensajes):
        r = cliente.chat.completions.create(
            model=modelo, messages=mensajes, temperature=0, max_tokens=200,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}})
        return r.choices[0].message.content or ""
    return llamar


def interpretar(respuesta: str):
    """(tipo, confianza, valido). Un tipo fuera del catálogo se convierte en 'otro' y se marca inválido."""
    try:
        d = json.loads(respuesta)
        tipo = str(d.get("tipo", "")).strip()
        conf = d.get("confianza")
        conf = float(conf) if conf is not None else None
    except (ValueError, TypeError, AttributeError):
        return OTRO, None, False
    if tipo not in ETIQUETAS:
        return OTRO, conf, False
    return tipo, conf, True


class ClasificadorLLM:
    def __init__(self, llamar, reintentos: int = 2):
        self.llamar = llamar
        self.reintentos = reintentos
        self.cache: dict[str, dict] = {}
        self.llamadas = 0

    def clasificar_uno(self, texto: str) -> dict:
        if texto in self.cache:
            return self.cache[texto]
        mensajes = [{"role": "system", "content": SISTEMA},
                    {"role": "user", "content": f"Texto del cliente: {texto}"}]
        resultado = {"tipo": OTRO, "confianza": None, "valido": False, "intentos": 0}
        for intento in range(1, self.reintentos + 2):
            self.llamadas += 1
            tipo, conf, ok = interpretar(self.llamar(mensajes))
            resultado = {"tipo": tipo, "confianza": conf, "valido": ok, "intentos": intento}
            if ok:  # DeepSeek puede devolver contenido vacío si el JSON sale mal: se reintenta
                break
        self.cache[texto] = resultado
        return resultado

    def clasificar(self, textos):
        return [self.clasificar_uno(t) for t in textos]
