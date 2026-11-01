"""Tipos de caso de soporte. 15 problemas y 2 felicitaciones, que son las 17 frases base de los datos,
más 'otro' para lo que no encaja (necesario para medir qué pasa ante texto fuera del catálogo)."""

OTRO = "otro"

TIPOS = {
    "producto_danado": "El producto llegó roto, golpeado o con daños visibles.",
    "pedido_no_llega": "El pedido no ha llegado y ya pasó la fecha prometida (se sabe que sigue pendiente).",
    "cambio_direccion": "El cliente quiere cambiar o corregir la dirección de entrega.",
    "producto_distinto_descripcion": "El producto recibido no corresponde a la descripción, fotos o ficha de la página.",
    "equipo_no_enciende": "Un equipo o aparato recibido no enciende o no funciona y el cliente pide cambio.",
    "talla_incorrecta": "Se recibió una talla o número distinto al pedido.",
    "entrega_no_recibida": "El sistema o la transportadora dice que se entregó, pero el cliente no recibió nada.",
    "pedido_incompleto": "El pedido llegó, pero falta uno o más productos o accesorios.",
    "cupon_no_aplicado": "No se aplicó el cupón, código o descuento prometido.",
    "cobro_duplicado": "Le cobraron dos veces el mismo pedido.",
    "reembolso_cancelado": "Pide el reembolso o reintegro de un pedido cancelado.",
    "pago_rechazado_con_cargo": "El pago fue rechazado o falló, pero el dinero sí salió de la cuenta.",
    "actualizar_datos": "Quiere actualizar o corregir sus datos personales o de contacto.",
    "eliminar_cuenta": "Pide eliminar su cuenta y sus datos.",
    "login_app": "No puede iniciar sesión o acceder a la app o a su cuenta.",
    "felicitacion_cambio": "Agradece o felicita por la rapidez o facilidad de un cambio.",
    "felicitacion_atencion": "Felicita o agradece la atención del asesor o del equipo de soporte.",
}
ETIQUETAS = list(TIPOS) + [OTRO]

SISTEMA = (
    "Eres un clasificador de tickets de soporte de una tienda en línea colombiana. "
    "Clasifica el texto del cliente en EXACTAMENTE uno de estos tipos de caso:\n"
    + "\n".join(f"- {k}: {v}" for k, v in TIPOS.items())
    + f"\n- {OTRO}: cualquier cosa que no encaje claramente en los tipos anteriores (consultas generales, "
    "cotizaciones, preguntas, texto sin sentido).\n\n"
    "Reglas: no inventes tipos nuevos; si dudas entre un tipo y 'otro', elige 'otro'. "
    "Distingue 'pedido_no_llega' (sigue pendiente, sin que nadie diga que se entregó) de "
    "'entrega_no_recibida' (alguien afirma que ya se entregó, pero el cliente no lo recibió).\n"
    'Responde SOLO un objeto JSON con esta forma: {"tipo": "<tipo>", "confianza": <número entre 0 y 1>}'
)
