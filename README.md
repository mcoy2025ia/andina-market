# Andina Market · Prueba técnica: Líder Técnico de Datos, BI y Automatización

Autor: Manuel Alberto Coy Benavides. Entrega del 31 de octubre de 2026.

## Uso de IA generativa (declaración)
Usé **Claude (Anthropic)** como asistente durante toda la prueba: para proponer el diseño, escribir y probar código (ETL, pruebas, SQL, DAX, experimento de optimización), redactar los documentos y revisar el PR. **Las decisiones de negocio son mías** (atribuir la venta a `fecha_pedido`, enviar a cuarentena los 20 pedidos con fecha de 2027, criterios neutros para comparar plataformas, trabajar más cerca de Fabric/Spark, agregar la capa Bronze en Parquet). Ejecuté y verifiqué el código en mi equipo, y puedo explicar y modificar cada pieza en la sustentación.

## Cómo ejecutarlo desde cero
Requisitos: Python 3.12 o superior. Las pruebas con Spark son opcionales y se omiten solas si falta algo: necesitan PySpark y Java; en Windows, además, Python 3.11 (con PySpark 3.5 y Python 3.12 se cae el *worker* de Python) y, para la prueba de SQL, `HADOOP_HOME` con `winutils.exe`.
```bash
python -m venv finanzauto
source finanzauto/Scripts/activate        # Windows (Git Bash). En Mac/Linux: source finanzauto/bin/activate
pip install -r requirements.txt
# copiar los CSV de la prueba en data/original/ (clientes, pedidos, pagos, tickets_soporte)
python scripts/cargar_datos.py --desde-cero   # carga Bronze (Parquet) + Silver + cuarentena + Gold y verifica totales
python -m pytest -q                           # pruebas
python scripts/catalogo_calidad.py            # regenera docs/02_catalogo_calidad.md
python scripts/recalculo_independiente.py data/original   # recalcula las cifras con pandas, sin usar el ETL
```
La carga termina con `CARGA CORRECTA` si los totales coinciden: 6.040 clientes, 19.270 pedidos y 20.124 pagos válidos, 7.925 filas de venta neta diaria y venta neta total de 14.177.333.600. Volver a correrla sin `--desde-cero` no inserta ni actualiza nada (idempotencia). Cada corrida es una transacción: si se cae a la mitad no deja Silver sin Gold, y basta con volver a ejecutarla. Tras cambiar la definición de venta, `--recalcular-gold` recalcula todos los días. Para Spark local: `pip install -r requirements-spark.txt`.

## Dónde está cada punto de la prueba
| Punto | Entregable |
|---|---|
| 1.1 SQL: venta neta mensual con variación y recompra por cohorte, con su lectura de 3 líneas | `sqlserver/01_ventas_recompra.sql` (T-SQL), `duckdb/`, `fabric/sql/`, `databricks/sql/`, `docs/01_sql_lectura.md` |
| 1.2 Catálogo de calidad de datos (15 problemas, con conteos y tratamiento) | `docs/02_catalogo_calidad.md`, `scripts/catalogo_calidad.py` |
| 1.3 ETL incremental e idempotente, cuarentena, venta neta diaria, pruebas | `src/shared/andina_etl/`, `tests/`, `scripts/cargar_datos.py`; versión Spark en `fabric/notebooks/` y `src/shared/spark/` |
| 1.4 DAX | `fabric/semantic_model/medidas.dax`, `docs/03_dax.md` |
| 1.5 Optimización de la consulta de 50M de pedidos | `sqlserver/optimizacion/`, `docs/05_optimizacion.md` |
| 2 Arquitectura y decisiones (2 páginas) | `docs/04_arquitectura.pdf` (fuente HTML en la misma carpeta) |
| 3.1 Revisión del PR y versión corregida | `docs/06_liderazgo.md`, `src/shared/reporte_ventas.py`, `tests/test_reporte_ventas.py` |
| 3.2 Situaciones | `docs/06_liderazgo.md` |
| Modelo de datos en SQL Server / Fabric Warehouse | `sqlserver/ddl_tsql.sql` |
| Opcional: clasificar con IA los tickets y medir su calidad | `docs/07_clasificacion_ia.md`, `src/shared/tickets_ia/`, `scripts/clasificar_tickets.py` |

El detalle técnico del ETL (formatos, reglas, idempotencia, limitaciones) está en `README_ETL.md`.

## Decisiones de negocio
- **Venta neta** = `valor_bruto − descuento`, solo de pedidos `ENTREGADO`, atribuida a `fecha_pedido`.
- Rango válido: 2025-01-01 a 2026-09-30. Los 20 pedidos de 2027 van a cuarentena.
- Un pedido con cliente inexistente se conserva (la venta es real) y se marca.
- Las personas se cuentan con `v_cliente_maestro`: los 40 clientes duplicados por documento cuentan una vez (6.040 clientes, 6.000 personas).
- Recompra: un segundo pedido entregado, en una fecha posterior, dentro de 1, 3 o 6 meses calendario del primero; solo cuenta a quien ya tiene la ventana completa dentro de los datos.

## Resultados que vale la pena destacar
- La venta mensual se estancó desde diciembre de 2025 (entre 780 y 950 millones); la variación anual (+738 % en enero de 2026, +23 % en septiembre) refleja una base de 2025 muy baja, no un crecimiento sostenido.
- TIENDA cayó 51 % entre junio y septiembre de 2026 (217,6 a 105,8 millones) mientras APP creció.
- La recompra a 3 meses bajó de 63,2 % en las cohortes de 2025 a 49,2 % en las de 2026 (a 1 mes, de 32,1 % a 26,1 %). Los datos muestran el deterioro, no su causa.
- 122 pedidos entregados no tienen ningún pago, y 345 pagos pertenecen a pedidos rechazados: hallazgos de negocio para escalar.

## Qué se probó y qué no (por honestidad técnica)
| Pieza | Estado |
|---|---|
| ETL local con DuckDB, reglas, idempotencia, incremental | Probado con pruebas automáticas (85) y con los datos reales, incluidos caída a mitad de corrida, pago que llega antes que su pedido y pedido que pasa a inválido |
| Reglas en PySpark | Probadas en Spark 3.5.3 local (Python 3.11, Windows), con resultados idénticos a la versión DuckDB en las pruebas y con los datos reales (`verificar_paridad_real.py`) |
| SQL de venta neta y recompra | Ejecutado en DuckDB y en Spark SQL local; cifras confirmadas por un recálculo independiente en pandas (`scripts/recalculo_independiente.py`). La versión T-SQL es un texto paralelo revisado a mano, **no ejecutado en SQL Server** |
| Optimización | Experimento en SQLite con datos sintéticos; muestra la forma del problema, no los tiempos de SQL Server |
| DAX | **No ejecutado**; los valores esperados están en `docs/03_dax.md` |
| Celdas Delta del notebook (MERGE, rutas de Fabric), DDL, Databricks | **No ejecutados** en esas plataformas |
| Tickets de soporte | No se cargan en el ETL; los tratamientos propuestos están en el catálogo |
| Clasificación de tickets con IA | Ejecutada contra la API real de DeepSeek (Flash y V4 Pro). Los 2.125 tickets se clasificaron (34 textos distintos, 0 respuestas inválidas) y el costo medido fue de unos USD 0,03. En los conjuntos de prueba ambos modelos sacan 1,000 y las reglas sacan 0,627 en frases nuevas, pero esas frases son sintéticas y la etiqueta de referencia la propuso la IA, así que **no demuestran que el LLM sirva con tickets reales**. Pendiente: revisión de las 34 etiquetas por el autor y un conjunto de tickets reales etiquetados por personas. Detalle en `docs/07_clasificacion_ia.md` |

## Para la sustentación: cambios en vivo previstos
Cambiar la atribución de `fecha_pedido` a `fecha_entrega`; añadir una regla (por ejemplo, descuento mayor al 50 %); agregar el canal MARKETPLACE; cambiar la ventana de recompra a meses calendario. Los parámetros de negocio viven en `src/shared/andina_etl/config.py` y las reglas en `rules.py`. Tras el cambio: `python scripts/cargar_datos.py --recalcular-gold` (o `--desde-cero`); los totales de referencia de `cargar_datos.py` dejarán de coincidir, y es lo esperado. Una regla nueva de pedidos retira de Silver y de Gold los pedidos ya cargados que la incumplan (los pagos solo se revalidan dentro de la ventana del watermark).
