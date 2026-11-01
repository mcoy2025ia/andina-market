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

## Preguntas para practicar

1. ¿Qué se revierte si falla después de Silver? ¿Qué ocurre con Bronze?
2. ¿Qué protege el lock y qué no?
3. ¿Por qué el incremental de pagos aún lee un snapshot antes de filtrar?
4. ¿Por qué no se borran automáticamente filas ausentes?
5. ¿Qué diferencia hay entre venta, recaudo y reembolso?
6. ¿Qué necesitarías para afirmar que DAX está probado?
7. ¿Por qué un 100 % sintético no permite desplegar el clasificador sin otra evaluación?
8. ¿Qué pruebas cambiarían al modificar la definición de venta?

El ensayo técnico fue ejecutado por la herramienta. La práctica oral y la capacidad de modificar/explicar el código son responsabilidad del autor; no se declaran realizadas por él.
