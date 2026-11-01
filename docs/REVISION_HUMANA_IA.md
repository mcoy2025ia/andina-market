# Revisión humana de clasificación

## Material preparado

`revision_etiquetas_34.csv` conserva las 34 descripciones y la propuesta anterior de IA. `anotador_1`, `anotador_2`, `decision_final` y `motivo` están vacíos deliberadamente. Los textos se marcan como desarrollo: ya se utilizaron para crear reglas y no son evaluación independiente.

1. Cada anotador asigna una etiqueta de `src/shared/tickets_ia/taxonomia.py` sin copiar la columna del otro.
2. En discrepancias, discutir el significado y completar decisión final y motivo. Incluso si coinciden, completar la decisión final.
3. Diferenciar `pedido_no_llega` (pendiente) de `entrega_no_recibida` (declarada entregada pero negada por el cliente).
4. Usar `otro` cuando no exista tipo aplicable; no elegir una categoría solo por una palabra aislada.
5. Ejecutar `python scripts/revision_etiquetas.py auditar docs/revision_etiquetas_34.csv`.

La auditoría verifica campos/taxonomía, calcula acuerdo y kappa cuando es definible y detecta textos normalizados repetidos entre particiones. No acredita que anotaron personas ni detecta todas las paráfrasis. Es necesario revisar semánticamente grupos de textos parecidos y documentar la procedencia del conjunto nuevo.

## Evaluación real futura

Conseguir tickets nuevos autorizados, minimizar información personal, separar desarrollo y evaluación por grupo semántico y reservar la evaluación antes de ajustar reglas/prompts. Mantener fecha, versión de taxonomía, modelo y prompt con los resultados.

El evaluador existente `tickets_ia/metricas.py` calcula exactitud, F1 por clase, macro, matriz y consistencia. Para decisiones productivas, añadir intervalos acordes con tamaño/estratificación de la muestra y analizar los errores de mayor impacto. Esa decisión estadística y la muestra real siguen pendientes; no se simulan con etiquetas de otra IA.

Los LLM de la entrega empataron en frases sintéticas. La coincidencia no prueba generalización ni permite elegir entre modelos. La confianza devuelta por la API no está calibrada; el cliente marca revisión humana y no autoruta casos.
