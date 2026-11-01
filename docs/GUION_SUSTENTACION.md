# Guion de sustentación y ensayo

## Exposición de diez minutos

| Tiempo | Punto / pestaña | Mensaje |
|---|---|---|
| 0:00–1:00 | 1.1 SQL | Definición de venta, total y señal de TIENDA; separar dato de causa |
| 1:00–2:00 | 1.2 Calidad | Normalizar, marcar o aislar; mostrar conteos sin sumar reglas solapadas |
| 2:00–3:20 | 1.3 Python | Bronze, hash, watermark, cuarentena, transacción, estrella y compuerta |
| 3:20–4:10 | 1.4 DAX | Numerador/denominador coherentes y comparación de períodos equivalentes |
| 4:10–5:00 | 1.5 Optimización | CAST/rangos; evidencia SQLite y límite de SQL Server |
| 5:00–6:30 | 2.1–2.2 | Arquitectura propuesta y elección condicionada a piloto/costo/equipo |
| 6:30–7:30 | 2.3–2.4 | CI, publicación validada y plan de 90 días |
| 7:30–8:40 | 3.1–3.2 | Revisión constructiva, respuesta al incidente y estándares claros |
| 8:40–9:30 | Opcional IA | Resultados guardados y límites del conjunto sintético |
| 9:30–10:00 | Cierre | Qué está validado localmente y qué falta en destino |

## Ensayo ejecutable

`python scripts/ensayar_cambio.py` crea datos sintéticos y base temporales. Primero MARKETPLACE es rechazado; después se añade al mapa de canales, se recalcula y se verifica un incremento exacto de 90.000. Restaura el mapa al terminar. No modifica los originales ni acredita paridad Spark del cambio hipotético.

## Mapa de cambios en vivo

| Cambio pedido | Archivos / pruebas a considerar | Qué explicar |
|---|---|---|
| Canal nuevo | `rules.py`, espejo Spark, catálogos/DDL, SQL, modelo y reporte | El ensayo local demuestra el flujo; el contrato de cada destino también debe evolucionar |
| Descuento máximo | Reglas pandas/Spark y pruebas; recalcular histórico afectado | Registros cargados que pasan a inválidos se retiran y corrigen Gold |
| Fecha pedido → entrega | `store.py`, `star.py`, SQL y DAX; calendario | Es cambio de negocio, no una sustitución visual; nueva referencia esperada |
| Ventana recompra | Cuatro SQL y plantilla, madurez y denominador | Meses calendario no equivalen a 30/90/180 días fijos |
| Etiqueta de tipo de caso | `etiquetas.py`, `star.py`, espejo Spark y pruebas | Solo una decisión humana llega a `tipo_caso`; la propuesta vive aparte y no se mezcla |
| Destinatario del reporte | `reporte_envio.py` y `despachar_reporte.py` | La identidad es el hash del contenido: cambiar el destinatario no reenvía lo ya entregado |

## Preguntas para practicar

Sobre el ETL y las decisiones de negocio:

1. ¿Qué se revierte si falla después de Silver? ¿Qué ocurre con Bronze?
2. ¿Qué protege el lock y qué no?
3. ¿Por qué el incremental de pagos aún lee un snapshot antes de filtrar?
4. ¿Por qué no se borran automáticamente filas ausentes?
5. ¿Qué diferencia hay entre venta, recaudo y reembolso?
6. ¿Qué necesitarías para afirmar que DAX está probado?
7. ¿Por qué un 100 % sintético no permite desplegar el clasificador sin otra evaluación?
8. ¿Qué pruebas cambiarían al modificar la definición de venta?

Sobre el traslado a Delta (IA-R02):

9. En DuckDB toda la corrida es una transacción. En Delta no existe esa garantía entre
   tablas: ¿qué pasa si el proceso muere después de escribir `fact_pedido` y antes de
   `fact_pago`, y cómo evita el diseño que alguien lea ese estado?
10. ¿Qué parte del notebook está probada y cuál no, y por qué esa frontera está ahí?
11. ¿Por qué las claves de dimensión no pueden renumerarse entre cargas?

Sobre las etiquetas y la evaluación (IA-R03, IA-R04):

12. Si alguien pide «publicar ya las etiquetas que sacó el modelo», ¿qué responde el
    sistema y por qué está hecho así?
13. La exactitud sobre la muestra reservada fue 0,560 con intervalo 0,423–0,688.
    ¿Qué se puede afirmar con eso y qué no?
14. ¿Qué es un «error crítico» aquí, quién debería definirlo y por qué no basta la
    exactitud media?
15. ¿Por qué la asociación de etiquetas va por hash del texto y no por `id_ticket`?

Sobre el reporte (IA-R05):

16. ¿Por qué la identidad del reporte es el hash del contenido y no la fecha?
17. ¿Qué distingue un fallo que se reintenta de uno que no, y qué pasa si se agotan
    los reintentos?

## Qué sigue sin estar acreditado

El ensayo técnico lo ejecutó la herramienta. La práctica oral y la capacidad de
modificar y explicar el código son responsabilidad del autor: **no se declaran
realizadas por él**. Un simulacro asistido tampoco sustituye esa práctica; sirve para
encontrar los puntos donde la explicación todavía no se sostiene.
