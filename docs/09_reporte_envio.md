# Transporte del reporte diario (IA-R05)

**Corte:** 1 de noviembre de 2026. Cubre el pendiente IA-R05 y deja preparado U07.

Qué cierra: el **diseño, el código y las pruebas de integración** del transporte, con
los cuatro casos simulados (éxito, fallo, reintento y duplicado) y la configuración
documentada sin secretos. Qué **no** cierra: haber enviado un correo real. Eso exige
destinatarios, canal y horario acordados (U07) y una autorización explícita.

## 1. Por qué no basta con «mandar el correo»

Un reporte diario automatizado falla de tres formas que el código ingenuo no cubre:

- **Se envía dos veces.** El proceso se reintenta tras una caída y la misma cifra
  llega dos veces. Quien la lee no sabe cuál vale.
- **Se reintenta lo que no tiene arreglo.** Un buzón inexistente no mejora al tercer
  intento; solo consume la ventana de entrega y oculta el error real.
- **Se pierde en silencio.** El envío falla, nadie se entera, y el informe de la
  mañana simplemente no está.

## 2. Cómo lo resuelve `src/shared/reporte_envio.py`

| Problema | Mecanismo |
|---|---|
| Duplicado | La identidad del reporte es el **hash de su contenido**. El registro `envios.json` guarda lo ya entregado; si vuelve el mismo contenido, se omite sin tocar el transporte. Si el dato cambió, la identidad cambia y sí se envía: es otro reporte. |
| Reintento | Solo ante `ErrorTransporteTemporal`, con espera creciente (0,5 s, 1 s, 2 s…) y un máximo configurable. |
| Fallo definitivo | `ErrorTransportePermanente` corta en el primer intento. |
| Pérdida silenciosa | Un fallo se anota como `FALLIDO`, **no** como enviado, así que la siguiente corrida lo reintenta. El registro deja rastro de cada intento. |
| Envío accidental | El transporte por defecto escribe a disco. Para que salga un correo hacen falta tres cosas a la vez: destinatarios, `autorizado=True` y un `TransporteSMTP` inyectado a propósito. |
| Concurrencia | El despacho corre bajo el mismo lock de archivo que el resto de la operación local. |

## 3. Configuración, sin secretos

La configuración guarda el **nombre** de la variable de entorno con la credencial,
nunca su valor. El registro de envíos tampoco la toca; hay una prueba que lo verifica.

```bash
# Variables de entorno (en el entorno, en .env.local o en el gestor de secretos del
# orquestador; .env.local no se versiona).
REPORTE_SMTP_PASSWORD=...        # solo el valor vive aquí
```

```bash
# Vista previa local: no abre ninguna conexión.
python scripts/despachar_reporte.py --db data/warehouse.duckdb --dia 2026-09-30

# Qué se ha despachado ya.
python scripts/despachar_reporte.py --out .local/reportes --historial

# Envío real: requiere la decisión de U07. No ejecutar sin ella.
python scripts/despachar_reporte.py --db data/warehouse.duckdb --dia 2026-09-30 \
    --transporte smtp --autorizar \
    --para finanzas@empresa --de etl@empresa \
    --servidor smtp.empresa --puerto 587 --credencial-en REPORTE_SMTP_PASSWORD
```

Lo que falta decidir (U07), y que el código deja como parámetro en vez de inventarlo:

| Decisión | Dónde entra |
|---|---|
| Destinatarios y remitente | `--para`, `--de` |
| Canal y servidor | `--transporte`, `--servidor`, `--puerto` |
| Horario y día reportado | `--dia` y el programador que lo invoque |
| Qué hacer si el dato no está validado | Hoy `preparar` **falla** si la publicación no concilia: no se envía un reporte sobre datos no validados |
| Reintentos aceptables | `--reintentos` |

## 4. Qué está probado

`tests/test_reporte_envio.py`, con transportes falsos y sin abrir ninguna conexión:

- envío correcto registrado con su identidad y su marca de tiempo;
- el mismo contenido no se envía dos veces, y el transporte ni se invoca;
- un contenido distinto sí se envía, aunque sea el mismo proceso;
- fallo transitorio reintentado con espera creciente hasta lograrlo;
- reintentos agotados: queda `FALLIDO` y la corrida siguiente lo reintenta;
- fallo permanente: un solo intento;
- sin autorización, sin destinatarios o sin remitente no se despacha nada;
- la credencial no aparece en el registro, pero sí el nombre de su variable;
- un registro corrupto detiene el despacho en lugar de reenviarlo todo.

**No ejecutado:** `TransporteSMTP` contra un servidor real, y por tanto la
correspondencia entre las excepciones de `smtplib` y la clasificación
temporal/permanente. Se valida junto con U07.
