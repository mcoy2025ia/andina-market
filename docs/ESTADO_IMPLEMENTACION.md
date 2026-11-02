# Estado de implementación — tareas A01–A18

**Corte:** 1 de noviembre de 2026. Fuente de estado para README, pendientes y presentaciones.

Repositorio privado: [mcoy2025ia/andina-market](https://github.com/mcoy2025ia/andina-market).

## Resumen de lo implementado

El flujo local ahora carga también soporte cuando existe su CSV, construye un modelo estrella `gold.*`, concilia Gold contra Silver antes de confirmar, registra publicación validada y excluye escritores concurrentes. Las nuevas herramientas permiten reconciliar snapshots sin aplicar bajas, preparar un reporte sin enviarlo y ensayar respaldo/restauración en destinos nuevos.

No se ha desplegado infraestructura ni ejecutado SQL Server, Power BI, Fabric o Databricks como parte de este bloque. Las extensiones de orquestación son locales; el notebook Delta no hereda automáticamente estas funciones.

## Matriz de las 18 tareas

| Tarea | Resultado material | Validación / límite restante |
|---|---|---|
| A01 · Estados y cifras | Este registro, README y documentos reconciliados; inventario anterior marcado histórico | Fecha administrativa 21/31 octubre pendiente de confirmación del autor |
| A02 · Evidencias | `scripts/verificar_entrega.py`: pruebas, carga aislada, segunda carga, hashes de hechos y recálculo independiente | Evidencia nueva en `docs/evidencia/ejecucion_actual/`; no modifica base de trabajo |
| A03 · Paquete y Git | Repositorio privado creado y cargado; `.env.example`; ZIP por archivos versionados con SHA-256 y exclusiones | Escaneo por patrones no es garantía absoluta; no se publicaron CSV originales ni claves |
| A04 · Meses vacíos | Calendario enero 2025–septiembre 2026 en DuckDB, T-SQL y SQL generado Spark | Probado en DuckDB; ejecución Spark en CI separada; T-SQL pendiente en destino |
| A05 · Contratos de cifras | Pruebas Silver → Gold diario → hechos → SQL mensual; filtros de estados y denominadores | DAX necesita validación de motor E03; no se considera ejecutado por existir el código |
| A06 · Modelo estrella | `star.py` con dimensiones estables y hechos; `cargar_modelo_sqlserver.py` prepara plan o carga transaccional | Modelo local probado; cargador SQL Server preparado, sin ejecución remota; hechos se reconstruyen por lote |
| A07 · Esquema de entrada | Cabeceras únicas, columnas requeridas, codificación y ancho CSV; extras reportados | Fallo estructural revierte corrida; esquema Spark de ingesta no sustituye este contrato local |
| A08 · Dinero y catálogos | Parseo exacto de pesos enteros; fracciones/no finitos/fuera de BIGINT no se truncan; opción decimal documentada | Reglas replicadas en Spark; catálogo de categorías y migración a centavos requieren U03 |
| A09 · Relaciones e incidencias | Revalidación de cliente tardío; `calidad_incidencias` abierta/resuelta sin borrar historial | Solo se resuelven IDs reevaluados; propietario humano y workflow organizacional pendientes |
| A10 · Correcciones y ausencias | `--reconciliar` relee pagos fuera de ventana; script informa bajas candidatas, nuevos y cambios | No aplica borrados por ausencia sin contrato de snapshot; U04 pendiente |
| A11 · Soporte | Bronze/Silver y `gold.fact_ticket`; fechas incoherentes conservadas con flags y SLA nulo | Asociación de clasificación preparada por tabla versionada; no se autoruta ni se etiqueta como validada por humanos |
| A12 · Cliente LLM | JSON/tipos/confianza validados; timeout, reintentos acotados, presupuesto, caché y versión de prompt | Pruebas sin red; confianza no calibrada; todas las salidas requieren política humana antes de uso productivo |
| A13 · Evaluación humana | Plantilla de 34 textos, dos anotadores, decisión final, auditoría de campos, acuerdo/kappa y fugas exactas | Pendiente revisión humana y muestra nueva; auditoría de formato no acredita independencia semántica |
| A14 · Reporte | Vista previa HTML local, identificador por contenido, escritura idempotente y publicación comprobada | No envía correo; destinatarios/horario y ODBC pendientes |
| A15 · CI | Comando local y workflow GitHub para núcleo y Spark separados; acciones fijadas por SHA | Resultado remoto en Actions; protecciones de rama y despliegue de producción no configurados |
| A16 · Publicación | Conciliación por día/canal/categoría; umbrales opcionales de cuarentena, volumen, total y frescura; rollback | Los umbrales operativos requieren aprobación; por defecto solo conciliación estructural del indicador |
| A17 · Recuperación | Lock por base, fallo multietapa probado, respaldo en frío y restauración a archivo nuevo | No cubre bloqueo distribuido ni recuperación Delta; RPO/RTO reales pendientes |
| A18 · Sustentación | Guion de diez minutos, mapa de archivos y ensayo ejecutable de MARKETPLACE en copia temporal | El autor debe practicar y demostrar comprensión; no se considera ensayado por él |

## Cómo verificar sin tocar los datos de trabajo

```powershell
python scripts/ci_local.py
python scripts/verificar_entrega.py --raw data/original --caso
python scripts/ensayar_cambio.py
python scripts/empaquetar.py
```

La verificación usa un directorio temporal; el recálculo lee originales pero solo guarda resultados agregados. Las evidencias históricas de las presentaciones conservan sus conteos originales. El conteo vigente está en [resultado](evidencia/ejecucion_actual/resultado.json) y [salida pytest](evidencia/ejecucion_actual/pytest.txt).

## Bloque IA-R01 a IA-R05 (segunda revisión del 1 de noviembre de 2026)

Cinco pendientes que no dependían de credenciales de producción. Ninguno ejecuta SQL Server, Power BI, Fabric ni Databricks.

| Tarea | Resultado material | Validación / límite restante |
|---|---|---|
| IA-R01 · Impresión | `scripts/qa_impresion.py`: aplica las reglas `@media print` sobre pantalla, mide contra el área de `@page` y lee el texto de cada página del PDF ya impreso. Corregidos los bloques sin `break-inside`, el encabezado repetido de tablas y una página con una sola línea | 0 hallazgos sobre 102 páginas (52 + 48 + 2). El punto exacto de cada salto lo decide el paginador; se revisó por imagen. PDF en `evidencia/impresion/` |
| IA-R02 · Delta | `src/shared/spark/extensiones_spark.py` y notebook regenerado con soporte, contratos, estrella, incidencias y publicación por puntero de run | 19 pruebas contra PySpark real comparan la estrella completa con DuckDB fila a fila. `MERGE`, `DELETE` y `DESCRIBE HISTORY` **no ejecutados**: es E04 |
| IA-R03 · Etiquetas | `andina_etl/etiquetas.py` y `scripts/importar_etiquetas.py`: lote versionado, taxonomía, procedencia y asociación por hash de texto | `fact_ticket.tipo_caso` solo admite `REVISADA`; la propuesta va en `tipo_caso_propuesto`. Sin U05 no hay nada que importar y el script lo dice |
| IA-R04 · Evaluación | `tickets_ia/evaluacion.py` y `clasificar_tickets.py reservada`: intervalos de Wilson, errores críticos, fugas y telemetría de costo/latencia | Probado con partición sintética (reglas: exactitud 0,560; IC 95 % 0,423–0,688 sobre n = 50). No acredita desempeño real: falta U06 |
| IA-R05 · Reporte | `src/shared/reporte_envio.py` y `scripts/despachar_reporte.py`: duplicados por hash de contenido, reintento solo ante fallo transitorio, registro sin secretos | 14 pruebas con transportes falsos. `TransporteSMTP` **no ejecutado** contra un servidor real: falta U07 |

Queda abierto **IA-R06** (ensayo de la sustentación), que requiere al autor.

## Estado de los pendientes anteriores que cambió

- **P15:** QA de las nuevas presentaciones realizado en escritorio y móvil. **La impresión ya está certificada página a página** (IA-R01): auditoría reproducible con 0 hallazgos e inventario de las 102 páginas de los tres PDF.
- **P19:** nuevas salidas de pruebas, primera y segunda carga, modelo estrella y recálculo independiente disponibles. Spark se acredita por su job separado, no por la suite local que lo omite.
- **P20:** APP creció 19,22 % entre junio y septiembre de 2026; CSV agregado disponible.
- **P21:** TIENDA creció 59,79 % en ese intervalo de 2025 y cayó 51,37 % en 2026; no prueba causalidad ni ausencia de estacionalidad.
- **P02:** resolver por evidencia de la ejecución actual de Spark; las declaraciones anteriores, contradictorias, quedan como históricas.
- **P03–P08 y P16:** el código preparado no cierra las validaciones específicas de SQL Server, DAX o Delta cloud.

## Decisiones todavía tuyas

Fecha/forma de entrega; revisión de las 34 etiquetas; contrato de borrados y precisión monetaria; categorías gobernadas; objetivos y umbrales; destinatarios; acceso al destino y presupuesto; revocación de credenciales reales cuando aplique. La contraseña redactada del enunciado no se presume operativa.

## Verificación final del bloque

- Suite local con fuentes del caso: **175 pruebas aprobadas, 3 módulos Spark omitidos** por las restricciones de Spark en Windows con Python 3.12.
- Spark ejecutado aparte con Python 3.11 y Java 17: **24 pruebas aprobadas** (5 de paridad de reglas y 19 de las extensiones Delta, que comparan dimensiones y hechos contra DuckDB fila a fila). `test_sql_spark.py` sigue omitido en Windows por requerir `HADOOP_HOME`; se ejecuta en el job de CI. Nada de esto acredita ejecución Delta en Fabric/Databricks.
- Carga completa con los datos del caso tras los cambios de esquema: **6.040 / 19.270 / 20.124 / 7.925 y COP 14.177.333.600**, sin variación.
- [CI aprobada para el código 28c8338](https://github.com/mcoy2025ia/andina-market/actions/runs/41323664358): jobs local y Spark. [Salida Spark](evidencia/spark_ci/pytest.txt). Los cambios de IA-R01 a IA-R05 son posteriores y necesitan una CI nueva.
- Recálculo independiente: COP 14.177.333.600; segunda carga sin cambios en hechos.
- Navegador: 13 pestañas y 17 capítulos revisados en escritorio/móvil, sin errores JavaScript ni desbordamientos.
- Impresión: 102 páginas auditadas sin hallazgos; PDF de arquitectura regenerado tras ajustar su CSS de impresión.
