# Parte opcional: clasificar con IA las descripciones de `tickets_soporte.csv`

Código: `src/shared/tickets_ia/` (taxonomía, línea base, cliente LLM, métricas) y `scripts/clasificar_tickets.py`. Pruebas: `tests/test_tickets_ia.py`.

## Qué hay en los datos
2.125 tickets, pero solo **34 descripciones distintas**: 17 frases base (15 problemas y 2 felicitaciones), cada una escrita a veces en mayúscula inicial y a veces en minúscula. No hay ninguna columna con el tipo de caso. Por eso:
- Se clasifica cada texto distinto **una sola vez** y el resultado se propaga a los tickets (34 llamadas, no 2.125).
- Clasificar estos datos es casi trivial; un buen resultado aquí **no demuestra** que el método sirva con texto nuevo. Por eso la medición tiene dos conjuntos.

## Taxonomía
17 tipos (`src/shared/tickets_ia/taxonomia.py`) más `otro` para lo que no encaja. La etiqueta de las 34 descripciones reales (`datos/etiquetas_reales.csv`) la propuso el asistente de IA con la lectura literal de cada frase. **PENDIENTE DEL AUTOR: revisar las 34 etiquetas una por una y reemplazar esta frase por «las revisé y corregí N».** Distinción delicada: `pedido_no_llega` (sigue pendiente) frente a `entrega_no_recibida` (alguien afirma que ya se entregó).

## Cómo se mide la calidad
| Conjunto | Qué es | Para qué sirve |
|---|---|---|
| `reales` | Las 34 descripciones distintas, etiquetadas por el asistente (pendiente de revisión del autor) | Comprobar que el método cubre lo que ya existe |
| `generalizacion` | 150 frases **nuevas** con etiqueta conocida: paráfrasis, jerga, errores de escritura y 14 casos fuera del catálogo | Ver si generaliza. Las frases son **sintéticas**: las escribió Claude y no son tickets reales |

Métricas: exactitud, precisión, recall y F1 por tipo, F1 macro, matriz de confusión, lista de errores y **consistencia** entre dos ejecuciones independientes (cada ejecución crea su propio clasificador, así que la caché no cuenta). Resultados en `resultados/ia/`.

## Resultados medidos
Ejecutados el 31 de octubre de 2026, contra la API real de DeepSeek, con la clave en `.env.local` (no versionado). Configuración: modo «thinking» desactivado, `temperature=0`, salida JSON. La API aceptó esa configuración sin errores, así que la duda sobre `temperature=0` queda resuelta.

**Línea base con reglas de palabras clave** (ejecutada):
- `reales`: exactitud 1,000 (34 de 34). Esperable: las reglas se escribieron leyendo esas frases.
- `generalizacion`: **exactitud 0,627 (intervalo aproximado al 95 %: 0,55 a 0,70, con n = 150) y F1 macro 0,683**. Falla sobre todo en `producto_distinto_descripcion` (F1 0,20), `pedido_no_llega` (0,22), `producto_danado` (0,40) y `pedido_incompleto` (0,40). Y manda a `otro` demasiado (recall 0,93 pero precisión 0,19): cuando no reconoce la palabra, no sabe decir que no sabe.
- Un detalle que enseña: la primera versión de la regla de talla usaba la palabra suelta `talla` y clasificaba «la **pan**talla estrellada» como talla incorrecta (exactitud 0,620 antes de corregirlo con límites de palabra). Las reglas por palabras clave son frágiles justo ahí.
- **Contaminación:** esa corrección se hizo al ver el error en el conjunto de generalización, así que ese conjunto ya no es del todo independiente y el 0,627 es algo optimista. Además, las frases las escribió la misma IA que ayudó a escribir las reglas.

**Clasificador con LLM (DeepSeek)**:

| Conjunto | Modelo | Exactitud | F1 macro | Respuestas inválidas | Consistencia |
|---|---|---|---|---|---|
| `reales` (34) | deepseek-flash | 1,000 | 1,000 | 0 | 1,000 |
| `generalizacion` (150) | deepseek-flash | 1,000 | 1,000 | 0 | 1,000 |
| `reales` (34) | deepseek-v4-pro | 1,000 | 1,000 | 0 | 1,000 |
| `generalizacion` (150) | deepseek-v4-pro | 1,000 | 1,000 | 0 | 1,000 |

**Clasificación de los 2.125 tickets** con deepseek-flash: 34 llamadas (un texto distinto cada una), 0 respuestas inválidas. Resultado en `resultados/ia/tickets_clasificados_llm.csv`. Coincide al 100 % (2.125 de 2.125) con la línea base de reglas.

**Costo medido:** el saldo de la cuenta pasó de USD 2,98 a USD 2,95 entre la clasificación y la evaluación con deepseek-v4-pro (unas 400 llamadas en ese intervalo). Es decir, unos USD 0,03, con un error de ±0,01 por la precisión del saldo. La primera evaluación con deepseek-flash no entra en esa cifra porque se hizo antes de consultar el saldo.

**Cómo se leen estos resultados:**
- En `generalizacion` el LLM supera claramente a las reglas (1,000 frente a 0,627). Eso sí es un hecho medido.
- Pero los dos modelos sacan 1,000, así que este conjunto **ya no sirve para elegir entre ellos**, y es posible que sea demasiado fácil para distinguir cualquier LLM.
- Sobre los datos del caso, el LLM y las reglas coinciden al 100 %, porque los 34 textos son los mismos con los que se escribieron las reglas. **El caso no permite medir la ventaja del LLM sobre texto nuevo.**
- Las etiquetas de `reales` las propuso la IA, y el LLM las reproduce. Esa coincidencia no es una medida independiente.

**Qué falta para decidir si el LLM vale su costo:**
1. Revisión humana de las 34 etiquetas (lo hace el autor).
2. Un conjunto de tickets reales, etiquetados por personas, que no se haya usado para escribir reglas ni el prompt. En los datos del caso no hay más textos distintos para eso.
3. Una medición de costo más precisa que la del saldo con dos decimales, si el volumen crece.

## Cómo ejecutarlo
```bash
pip install -r requirements-ia.txt
# La clave va en .env.local (raíz del repositorio, ignorado por git) o en la variable de entorno:
#   DEEPSEEK_API_KEY=...
python scripts/clasificar_tickets.py evaluar --metodo llm --modelo deepseek-flash --repeticiones 2
python scripts/clasificar_tickets.py evaluar --metodo llm --modelo deepseek-v4-pro --repeticiones 2
python scripts/clasificar_tickets.py clasificar --metodo llm --modelo deepseek-flash   # etiqueta los 2.125 tickets
```
Si ambas fuentes tienen la clave, prevalece la variable de entorno. La suite de pruebas (`pytest`) **no** hace llamadas reales: usa una función falsa; las llamadas de arriba se ejecutaron a mano.

**Cómo leer el resultado:** el LLM aporta si en `generalizacion` supera con claridad el 0,627 de las reglas **y** el resultado se puede comparar entre modelos. Hoy se cumple lo primero y no lo segundo. Para decidir, mirar la matriz de confusión: ¿se equivoca entre tipos parecidos (aceptable) o inventa lo que no hay (grave)?

## Cómo mediría la calidad en producción
1. **Muestra etiquetada por personas**, estratificada por tipo y renovada cada mes, con suficientes ejemplos de los tipos raros. Es la única medida real; los conjuntos sintéticos solo comparan métodos.
2. **Exactitud y F1 por tipo con intervalo de confianza**, no solo el promedio: un 95 % global puede esconder un tipo crítico (por ejemplo, cobros duplicados) con 60 %.
3. **Acuerdo entre dos anotadores** (kappa) para saber qué tipos son ambiguos incluso para personas; ese es el techo del modelo.
4. **Tasa de `otro` y de respuestas inválidas** a lo largo del tiempo. Un aumento indica texto nuevo (producto, campaña, problema) que el catálogo no cubre.
5. **Confianza y revisión humana:** lo que el modelo clasifica con baja confianza va a una cola de revisión. Se comprueba que la confianza esté calibrada (la de 0,9 acierta cerca del 90 %).
6. **Consistencia:** el mismo texto, clasificado dos veces, debe dar la misma etiqueta.
7. **Impacto en el negocio:** que la clasificación mueva decisiones (enrutar tickets, medir causas de devolución); si nadie la usa, la precisión da igual.
8. **Seguridad de los datos:** solo se envía el texto, sin identificadores; en producción habría que revisar si el texto libre puede traer datos personales antes de enviarlo a una API externa.
