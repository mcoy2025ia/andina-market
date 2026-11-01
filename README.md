# Andina Market · Datos, BI y automatización

Autor de la solución: Manuel Alberto Coy Benavides. Revisión e implementación de mejoras: **1 de noviembre de 2026**.

Repositorio: https://github.com/mcoy2025ia/andina-market (privado).

> El enunciado fija entrega el 21 de octubre de 2026; la documentación inicial decía 31 de octubre. No se dispone de confirmación de prórroga. Estas fechas no se presentan como entrega aceptada.

## Estado vigente

El [estado de implementación](docs/ESTADO_IMPLEMENTACION.md) separa lo implementado, lo probado y lo pendiente. El [plan detallado](docs/PLAN_MEJORAS_Y_PENDIENTES.md) conserva las 18 tareas y sus dependencias humanas.

- ETL local con contratos de entrada, Bronze, Silver, cuarentena, incidencias vigentes y Gold.
- Modelo estrella local `gold.*` con claves estables, hechos y 2.125 tickets del caso.
- Compuertas de conciliación y umbrales configurables; una transacción confirma datos y publicación juntos.
- Calendario mensual completo, parseo monetario exacto, cliente tardío revalidado y modo de reconciliación de pagos.
- Cliente LLM con respuestas/reintentos/presupuesto controlados; las pruebas no usan API real.
- CI local, workflow GitHub separado para núcleo/Spark, empaquetado, vista previa de reporte y ensayo de restauración.
- Notebook Spark/Delta con las mismas extensiones que el flujo local (soporte, contratos, estrella, incidencias y publicación por puntero de run), con 19 pruebas que lo comparan contra DuckDB fila a fila.
- Etiquetas de tipo de caso versionadas y con procedencia: solo una decisión humana llega a `fact_ticket.tipo_caso`.
- Arnés de evaluación con intervalos de confianza, errores críticos y telemetría; transporte del reporte con reintentos y sin duplicados.
- Impresión de los entregables HTML auditada página a página.

**La ejecución en SQL Server, DAX y Delta cloud permanece pendiente.** El notebook ya incluye las extensiones, pero no se ha ejecutado en Fabric ni en Databricks: `MERGE`, `DELETE` y las rutas de plataforma siguen sin correr. El cargador de SQL Server está preparado, no ejecutado en un servidor.

## Ejecutar sin datos originales

Python 3.12 para el núcleo; Spark se valida por separado con Python 3.11 y Java 17.

```bash
python -m venv .venv
# Activar el entorno según la terminal.
pip install -r requirements.txt
python scripts/ci_local.py
python scripts/ensayar_cambio.py
```

El CI usa datos sintéticos en directorios temporales. Guarda resultados en `.local/ci/`; no reconstruye la base de trabajo.

## Verificar los datos del caso de forma aislada

Colocar los CSV autorizados en `data/original/` (no se versionan).

```bash
python scripts/verificar_entrega.py --raw data/original --caso
```

Ejecuta las pruebas, primera y segunda carga temporales y recálculo independiente. [Resultado agregado](docs/evidencia/ejecucion_actual/resultado.json) y [salida de pruebas](docs/evidencia/ejecucion_actual/pytest.txt). Las omisiones se conservan con su motivo; no equivalen a pruebas aprobadas.

Referencias sin cambios de datos/contrato: **6.040 clientes; 19.270 pedidos; 20.124 pagos; 7.925 filas de Gold; COP 14.177.333.600**. La segunda carga no inserta ni actualiza hechos. Soporte aporta 2.125 tickets cuando se incluye el cuarto CSV.

## Carga de trabajo y herramientas

```powershell
$env:PYTHONPATH = "src/shared"
python -m andina_etl --raw data/original --db .local/modelo.duckdb --bronze .local/bronze
python -m andina_etl --raw data/original --db .local/modelo.duckdb --bronze .local/bronze --reconciliar
python scripts/previsualizar_reporte.py --db .local/modelo.duckdb --dia 2026-09-30
python scripts/despachar_reporte.py --db .local/modelo.duckdb --dia 2026-09-30
python scripts/importar_etiquetas.py propuestas --db .local/modelo.duckdb --version reglas-2026-11-01
python scripts/clasificar_tickets.py reservada --metodo reglas --sintetica
python scripts/qa_impresion.py --pdf
python scripts/cargar_modelo_sqlserver.py --db .local/modelo.duckdb
python scripts/empaquetar.py
```

El reporte solo se guarda en disco: `despachar_reporte.py` usa por defecto un transporte de carpeta y se niega a enviar correo sin autorización explícita (U07). `importar_etiquetas.py revision` se niega a importar mientras la revisión humana (U05) siga vacía. El último comando crea `dist/andina-market.zip` usando archivos versionados y un manifiesto. El cargador SQL Server solo muestra el plan salvo que se solicite explícitamente aplicar a un entorno de pruebas.

`python scripts/cargar_datos.py --desde-cero` es un comando legado **destructivo sobre las rutas indicadas**; no hace falta para las verificaciones anteriores.

## Dónde está cada punto

| Punto | Entregable |
|---|---|
| 1.1 SQL | `sqlserver/01_ventas_recompra.sql`, `duckdb/`, `fabric/sql/`, `databricks/sql/`, `docs/01_sql_lectura.md` |
| 1.2 Calidad | `docs/02_catalogo_calidad.md`, contratos y reglas en `src/shared/andina_etl/` |
| 1.3 ETL | Pipeline, pruebas y herramientas de verificación; notebook Spark en `fabric/notebooks/` |
| 1.4 DAX | `fabric/semantic_model/medidas.dax`, `docs/03_dax.md` |
| 1.5 Optimización | `sqlserver/optimizacion/`, `docs/05_optimizacion.md` |
| 2 Arquitectura | `docs/04_arquitectura.html` y su PDF; operación en `docs/OPERACION_Y_RECUPERACION.md` |
| 3 Liderazgo | `docs/06_liderazgo.md`, `src/shared/reporte_ventas.py`, pruebas |
| Opcional IA | `docs/07_clasificacion_ia.md`, `src/shared/tickets_ia/`, revisión humana preparada, arnés de muestra reservada |
| Traslado a Delta | `docs/08_traslado_delta.md`, `src/shared/spark/extensiones_spark.py`, `tests/test_spark_extensiones.py` |
| Envío del reporte | `docs/09_reporte_envio.md`, `src/shared/reporte_envio.py`, `tests/test_reporte_envio.py` |

## Presentaciones y guía

- [Resolución punto por pestaña](docs/presentacion_resolucion_prueba.html).
- [Presentación ejecutiva y diagnóstico](docs/presentacion_entrega.html).
- [Guion de sustentación](docs/GUION_SUSTENTACION.md).
- [Storyline del deck para Finanzauto](docs/10_storyline_finanzauto.md): 18 láminas y 14 de apéndice, con el comportamiento de cada una.
- [Contratos y decisiones](docs/CONTRATOS_Y_DECISIONES.md).
- [Operación y recuperación](docs/OPERACION_Y_RECUPERACION.md).
- [Detalle actualizado del ETL](README_ETL.md).
- [Traslado de las extensiones a Delta y escenarios para la nube](docs/08_traslado_delta.md).
- [Configuración del envío del reporte, sin secretos](docs/09_reporte_envio.md).
- PDF de las presentaciones y auditoría de impresión en `docs/evidencia/impresion/`.

## Uso de IA generativa

La solución inicial declara asistencia de Claude en diseño, código y documentación. Codex asistió en la revisión, presentaciones e implementación del bloque A01–A18. Los resultados de ejecución se vinculan a evidencia; las decisiones humanas, revisión de etiquetas y pruebas de plataforma no se atribuyen a una persona si no se han realizado. El autor debe poder explicar y modificar cada pieza.

## Hallazgos de negocio

La venta se estabiliza desde diciembre de 2025. Entre junio y septiembre de 2026, APP sube 19,22 % y TIENDA cae 51,37 %. La recompra a tres meses pasa de 63,2 % en cohortes de 2025 a 49,2 % en 2026. Los datos describen diferencias, no prueban sus causas. [CSV agregado de evidencia](docs/evidencia/presentacion/ventas_mensuales.csv).
