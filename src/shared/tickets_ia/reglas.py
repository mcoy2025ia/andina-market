"""Línea base: clasificador por palabras clave. Es lo que cualquier solución con IA debe superar.
Las reglas se escribieron leyendo las 17 frases base de los datos reales. Una corrección (límite de
palabra en 'talla', para no confundir 'pantalla') se hizo al ver un error en el conjunto de
generalización, así que su exactitud ahí es algo optimista (ver docs/07_clasificacion_ia.md)."""
import re
import unicodedata

from .taxonomia import OTRO

# El orden importa: se devuelve la primera regla que coincide.
REGLAS = [
    ("felicitacion_cambio", r"(gracias|agradezco|felicit|excelente|muy bien|buen servicio).*cambio|cambio.*(rapid|agil|facil|sencill|gracias)"),
    ("felicitacion_atencion", r"gracias|felicit|excelente|buena atencion|buen trato|atencion de primera|atendieron muy bien"),
    ("eliminar_cuenta", r"elimin|borr|dar(me)? de baja|cerrar mi cuenta|suprimir|olvido|retiro de mis datos"),
    ("actualizar_datos", r"actualiz|datos personales|modificar mi|corregir mi|editar mi"),
    ("login_app", r"iniciar sesion|contrasena|clave|no puedo (entrar|ingresar|acceder)|no logro ingresar|login"),
    ("cobro_duplicado", r"dos veces|doble|duplicad|dos cargos|segunda vez|dos debitos"),
    ("pago_rechazado_con_cargo", r"(pago|transaccion).{0,40}(rechaz|fallid|no aprobad)|rechaz.{0,40}pago"),
    ("reembolso_cancelado", r"reembols|reintegro|devuelv.{0,25}(dinero|plata|valor)"),
    ("cupon_no_aplicado", r"cupon|descuento|codigo promocional|bono"),
    ("cambio_direccion", r"direccion"),
    ("talla_incorrecta", r"\btallas?\b"),
    ("pedido_incompleto", r"incompleto|falta"),
    ("producto_distinto_descripcion", r"no corresponde|descripcion|distint"),
    ("equipo_no_enciende", r"no enciende|no prende|no funciona"),
    ("producto_danado", r"dana(d|r)|roto|rota"),
    ("entrega_no_recibida", r"transportadora|entregado|entrego"),
    ("pedido_no_llega", r"no ha llegado|no llega|fecha prometida|retras"),
]
_COMPILADAS = [(t, re.compile(p)) for t, p in REGLAS]


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def clasificar_reglas(texto: str) -> str:
    n = normalizar(texto)
    for tipo, rx in _COMPILADAS:
        if rx.search(n):
            return tipo
    return OTRO
