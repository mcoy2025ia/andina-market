# Traslado de las extensiones locales al flujo Delta (IA-R02)

**Corte:** 1 de noviembre de 2026. Cubre el pendiente IA-R02 y prepara la ejecución E04.

Qué cierra este documento: el **diseño, el código y las pruebas** de llevar soporte,
modelo estrella, contratos, incidencias y publicación consistente al notebook
PySpark + Delta. Qué **no** cierra: haberlo ejecutado en Fabric o en Databricks. Eso
es E04 y requiere el entorno de U09.

## 1. Qué se trasladó

| Extensión local | Dónde vive ahora en Spark | Diferencia obligada |
|---|---|---|
| `andina_etl/tickets.py` | `extensiones_spark.validar_tickets` | Ninguna de criterio: mismas reglas, mismas banderas, mismo `row_hash`. |
| `andina_etl/star.py` | `pasos_dimensiones`, `pasos_hechos`, `comprobar_estrella` | El SQL cambia de dialecto (`sequence`/`explode` por `generate_series`, `weekday+1` por `isodow`, `element_at` por `list_extract`). El criterio de clave es idéntico. |
| `andina_etl/contracts.py` | `verificar_contrato` | La codificación se comprueba por presencia del carácter de reemplazo, no por excepción del decodificador: Spark no falla al leer bytes inválidos, los sustituye. |
| `andina_etl/operations.py` (incidencias) | `delta_sentencias_incidencias` | `INSERT ... ON CONFLICT` de DuckDB pasa a `MERGE INTO` de Delta. |
| `andina_etl/operations.py` (compuertas) | `validar_publicacion`, `sql_conciliacion` | Mismas compuertas y mismos umbrales vacíos por defecto. |
| Transacción DuckDB de toda la corrida | `run_id` + `publicacion_actual` + vistas `v_fact_*` | **Rediseño, no traducción.** Ver abajo. |

## 2. La única diferencia de fondo: publicar sin transacción

En local, `pipeline.ejecutar` envuelve la corrida entera en una transacción DuckDB. Si
algo falla a mitad, no queda nada a medias y basta con volver a ejecutar.

**Delta no tiene transacciones entre tablas.** Solo garantiza atomicidad por tabla. Una
caída después de escribir `gold_fact_pedido` y antes de `gold_fact_pago` deja el modelo
incoherente, y cualquier informe conectado lo leería.

El diseño adoptado invierte el orden del problema en lugar de fingir que no existe:

1. Los hechos se escriben **marcados con el `run_id`** de la corrida.
2. Se concilia Gold contra Silver al mismo grano (`sql_conciliacion`) y se aplican las
   compuertas (`validar_publicacion`).
3. **Solo si todo cuadra** se mueve el puntero `publicacion_actual`, que es una sola
   escritura y por tanto sí es atómica en Delta.
4. Los consumidores (Power BI, el reporte) leen las vistas `v_fact_*`, que filtran por
   el run publicado.

Consecuencia: mientras el puntero no se mueva, el consumidor sigue viendo **la carga
anterior completa**, nunca una a medias ni una que no pasó las compuertas. Es el
equivalente funcional de la transacción local, con el coste de que las tablas de hechos
retienen filas de runs no publicados hasta la siguiente limpieza.

Pendiente de acordar en U08: cada cuánto se purgan los runs no publicados y cuántas
versiones se conservan para `RESTORE`.

## 3. Qué está probado y qué no

`tests/test_spark_extensiones.py` ejecuta con PySpark real, sustituyendo las tablas Delta
por vistas temporales, y compara **fila a fila contra el almacén DuckDB**:

- reglas de soporte: misma cuarentena, mismos válidos, mismas banderas y mismo SLA nulo;
- las cuatro dimensiones, con sus claves sustitutas;
- los cuatro hechos;
- que una segunda construcción **no renumera** las dimensiones;
- que la conciliación detecta un Gold alterado y que las compuertas bloquean;
- que las vistas de publicación no muestran un run que todavía no se publicó;
- que el contrato rechaza cabecera repetida y columnas faltantes.

**No ejecutado, y por tanto no acreditado:** todo lo que exige un runtime Delta. Son las
funciones con prefijo `delta_` (`delta_refrescar_atributos_cliente`, `delta_publicar`,
`delta_sentencias_incidencias`) más `MERGE`, `DELETE` y `DESCRIBE HISTORY` del notebook,
y las rutas de Lakehouse o Volumes. Se escribieron con sintaxis estándar de Delta pero
no se han corrido en ninguna plataforma.

## 4. Escenarios para E04

Orden sugerido. Cada escenario indica qué ejecutar, qué debe pasar y qué evidencia
guardar. **Validar Fabric no acredita Databricks ni al revés**: se elige un destino y se
declara cuál.

| # | Escenario | Qué debe ocurrir | Evidencia a capturar |
|---|---|---|---|
| E04-01 | Primera carga completa | Cifras del caso: 6.040 clientes, 19.270 pedidos, 20.124 pagos, 7.925 filas Gold, venta neta 14.177.333.600 | Salida de la celda 12 |
| E04-02 | Segunda carga sin cambios | 0 insertados y 0 actualizados en las cuatro tablas; Bronze no vuelve a aterrizar | Resumen de la celda 9 y `bronze_manifest` |
| E04-03 | Archivo modificado | Solo cambian las filas con `row_hash` distinto; los días afectados se recalculan | `DESCRIBE HISTORY` de `silver_pedidos` |
| E04-04 | Cabecera alterada | La corrida se detiene en la celda 5 **antes** de tocar Bronze | Error del contrato y ausencia de versión nueva |
| E04-05 | Pago tardío fuera de ventana | El pago huérfano se relee aunque su `fecha_carga` quede fuera del watermark | Fila saliendo de cuarentena |
| E04-06 | Pedido que pasa a inválido | Sale de Silver, su día se recalcula y la venta baja | `numDeletedRows` y Gold del día |
| E04-07 | Incidencia que se resuelve | Pasa a `RESUELTA` sin borrar el registro de cuarentena | `calidad_incidencias` antes y después |
| E04-08 | Fallo entre tablas de hechos | El puntero **no** se mueve; `v_fact_*` siguen mostrando el run anterior completo | `publicacion_actual` y conteo de las vistas |
| E04-09 | Compuerta disparada | `PublicacionBloqueada`; hechos escritos pero no publicados | Traza y `publicacion_actual` sin cambios |
| E04-10 | Recuperación | `RESTORE` de la tabla a la versión previa y reejecución | Versiones Delta antes y después |
| E04-11 | Dimensiones estables | Tras varias cargas, las claves de canal, categoría y cliente no cambian | `gold_dim_*` entre corridas |
| E04-12 | Paridad final | Venta neta y conteos coinciden con DuckDB y con el recálculo independiente | Comparación lado a lado |

## 5. Cómo ejecutar

El notebook se **genera**: editar `src/shared/spark/extensiones_spark.py` o
`rules_spark.py` y regenerar con `python src/shared/spark/build_notebook.py`. No editar
el `.ipynb`, que `scripts/ci_local.py` comprueba que esté al día.

1. Subir los CSV a `Files/andina/raw/` (Fabric) o al Volume (Databricks).
2. Ajustar `PLATAFORMA` en la celda 1.
3. Ejecutar todas las celdas y recorrer la tabla de la sección 4.

Tras ejecutar, actualizar la tabla «Qué se probó y qué no» del `README.md` y
[ESTADO_IMPLEMENTACION.md](ESTADO_IMPLEMENTACION.md) con el destino concreto y la fecha.
Hasta entonces, E04 sigue abierto.
