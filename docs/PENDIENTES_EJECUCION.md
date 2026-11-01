# Pendientes de ejecución y evidencia

## 0. Contexto (léelo primero si no conoces el proyecto)

**Qué es.** Solución a una prueba técnica de selección para el cargo de Líder Técnico de Datos, BI y Automatización, de la empresa ficticia Andina Market. La empresa vende tecnología, hogar, moda y mercado por página web, app y tiendas físicas. Cada área calcula las ventas a su manera y la gerencia recibe cifras distintas. La prueba pide resolverlo.

**Plazos.** El enunciado fija la entrega el 21 de octubre de 2026 a las 11:59 p. m. (hora de Colombia). El README de la solución dice "entrega del 31 de octubre de 2026". Está sin resolver (P13). La sustentación dura 60 minutos.

**Qué se pidió (enunciado).**
- **Parte 1, resolución técnica (50 %):**
  1. SQL: venta neta mensual por canal con variación frente al mes anterior, y tasa de recompra por cohorte de registro a 1, 3 y 6 meses. Tres líneas de lectura.
  2. Calidad de datos: al menos cinco tipos de problemas, cuántos registros afectan y cómo se tratarían.
  3. Python: proceso incremental e idempotente que carga pedidos y pagos, aplica reglas, manda lo inválido a cuarentena y genera venta neta diaria por canal y categoría. Al menos tres pruebas.
  4. DAX: medidas de venta neta, ticket promedio y variación frente al mismo mes del año anterior.
  5. Optimización: una consulta que tarda más de 20 minutos con 50 millones de pedidos. Identificar problemas, reescribirla y proponer índices o particiones.
- **Parte 2, arquitectura y decisiones (30 %):** máximo dos páginas con diagrama a 12 meses, recomendación entre dos plataformas (por ejemplo Microsoft Fabric o Databricks) con costo, riesgo y capacidad del equipo, versionado, despliegue y monitoreo, y qué se entrega en los primeros 90 días.
- **Parte 3, liderazgo técnico (20 %):** revisar un pull request de un analista junior con errores intencionales (clasificados como bloqueante, importante o sugerencia, con su motivo) y proponer la versión corregida. Responder dos situaciones en máximo 10 líneas cada una: un incidente con cifra 40 % menor que llegó a presidencia, y un conflicto con un desarrollador senior que rechaza los estándares.
- **Opcional:** clasificar con IA las descripciones de los tickets y explicar cómo medir su calidad.

**Datos de la prueba.** Cuatro archivos CSV con errores intencionales:
- `clientes.csv` (6.040 filas): `id_cliente`, `nombre`, `documento`, `ciudad`, `canal_registro`, `fecha_registro`.
- `pedidos.csv` (19.734 filas): `id_pedido`, `id_cliente`, `fecha_pedido`, `canal`, `categoria`, `valor_bruto`, `descuento`, `estado`, `fecha_entrega`.
- `pagos.csv` (20.883 filas): `id_pago`, `id_pedido`, `fecha_pago`, `valor` (negativo = reembolso), `medio_pago`, `fecha_carga`.
- `tickets_soporte.csv` (2.125 filas): `id_ticket`, `id_cliente`, `id_pedido`, `fecha_creacion`, `canal`, `estado`, `fecha_cierre`, `descripcion`.

Estos archivos contienen datos personales (nombres, documentos). **No los compartas con ninguna IA externa.** Este documento no los incluye y no hace falta compartirlos para seguir los pasos.

**Definiciones del caso.**
- **Venta neta:** valor bruto menos descuento, solo de pedidos entregados (`ENTREGADO`), atribuida a la fecha del pedido. Rango válido: 1 de enero de 2025 a 30 de septiembre de 2026.
- **Persona:** clientes con el mismo documento cuentan como una sola persona (6.040 registros, 6.000 personas).
- **Recompra:** la persona tiene un segundo pedido entregado dentro de 1, 3 o 6 meses calendario del primero. La base son las personas con la ventana completa dentro de los datos.
- **Medallion:** Bronze es la copia cruda e inmutable; Silver es la capa limpia con reglas; Gold es la venta neta diaria lista para el negocio.
- **Cuarentena:** tabla donde van los registros inválidos, con la regla violada y la fila original.
- **Idempotencia:** ejecutar el proceso dos veces produce el mismo resultado que ejecutarlo una.
- **Watermark:** marca de la última `fecha_carga` de pagos ya procesada; se relee una ventana de tres días.

**Dónde está todo (repositorio `andina-market`).**
- `README.md` y `README_ETL.md`: cómo ejecutarlo y el detalle del ETL.
- `CLAUDE.md`: guía del proyecto y comandos.
- `src/shared/andina_etl/`: el ETL en Python con DuckDB (reglas, cuarentena, Gold).
- `src/shared/spark/`: las mismas reglas en PySpark y el generador del notebook.
- `scripts/cargar_datos.py`: carga completa con verificación de cifras.
- `sqlserver/`: DDL y consultas en T-SQL; `sqlserver/optimizacion/` tiene el experimento.
- `duckdb/`, `fabric/sql/`, `databricks/sql/`: las mismas consultas en otros dialectos.
- `fabric/semantic_model/medidas.dax`: medidas DAX.
- `fabric/notebooks/andina_etl_spark.ipynb`: notebook para Fabric o Databricks.
- `src/shared/reporte_ventas.py`: versión corregida del pull request.
- `src/shared/tickets_ia/` y `scripts/clasificar_tickets.py`: clasificación de tickets.
- `tests/`: pruebas automáticas.
- `docs/`: entregables escritos y la presentación `presentacion_entrega.html`.

**Qué ya está verificado (con ejecución).**
- Carga desde cero con las cifras de referencia; una segunda carga inserta 0 registros.
- 85 pruebas pasan con Python 3.12; con Python 3.11 y PySpark pasan 89.
- Paridad entre Spark y DuckDB con los datos reales.
- Venta neta, canal y recompra confirmados con un cálculo independiente en pandas.
- Llamadas reales a la API de DeepSeek: 2.125 tickets clasificados, costo de unos USD 0,03.

**Qué no está verificado.** T-SQL, DDL y DAX en sus plataformas; los notebooks en Fabric y Databricks; la conexión a SQL Server; la calidad de la clasificación con IA, porque las etiquetas de referencia no las ha revisado una persona.

**Cómo usar este documento.** La IA que te ayuda no tiene acceso al equipo ni a los datos. Tú ejecutas los comandos y le pegas las salidas. El prompt para esa IA está en `docs/PROMPT_PARA_IA.md`.

## Cómo usar este documento

Este documento lista los pendientes de la entrega (P01 a P21). Cada uno dice qué hacer, con qué herramienta, qué cifra debe coincidir y qué evidencia guardar. Sirve para que los ejecutes tú mismo, con o sin ayuda de una IA, y para que quede constancia de cada resultado.

## Antes de empezar

**Seguridad (urgente):** la clave de DeepSeek apareció en el chat y la contraseña de administrador del pull request estaba escrita en el código. Rota ambas antes de cualquier otra cosa (P17). **Nunca pegues una clave, contraseña o cadena de conexión en un chat, en un archivo del repositorio ni en un informe.** Si una salida de comando las muestra, redáctala (reemplaza el valor por `***`) antes de guardarla.

**Dónde guardar la evidencia:** crea una carpeta por pendiente, `docs/evidencia/P01/`, `docs/evidencia/P02/`, y así sucesivamente. Dentro, pon:

1. `resultado.md` con este formato:

```
# P01 · Nombre del pendiente
- Fecha:
- Quién lo ejecutó:
- Equipo y entorno (sistema, versión de Python, de SQL Server, de Power BI, etc.):
- Qué se ejecutó (comando, pasos o clics):
- Cifra de referencia esperada:
- Cifra obtenida:
- Estado: CONFIRMADO / DIFERENCIA / NO CONFIRMADO / BLOQUEADO
- Archivos de salida adjuntos:
- Observaciones:
```

2. Las salidas en bruto (texto, capturas de pantalla, CSV), sin credenciales.

**Cifras de referencia del caso** (las usan varios pendientes):

| Indicador | Valor esperado |
|---|---|
| Clientes válidos | 6.040 |
| Pedidos válidos | 19.270 |
| Pagos válidos | 20.124 |
| Filas de venta neta diaria (Gold) | 7.925 |
| Venta neta total (COP) | 14.177.333.600 |
| Pedidos entregados | 16.855 |
| Filas de la consulta mensual por canal | 63 (3 canales × 21 meses) |
| Recompra 2026 a 1, 3 y 6 meses | 26,1 %, 49,2 %, 57,1 % |
| Venta neta enero 2026 (medida DAX) | 948.592.900 |
| Venta neta septiembre 2026 (medida DAX) | 795.114.800 |
| Pruebas automáticas, Python 3.12 | 85 pasan, 2 se omiten |
| Pruebas automáticas, Python 3.11 con Spark | 89 pasan, 1 se omite |

**Orden sugerido:** P17, P13, P01, P19, P02, P04, P03, P16, P05, P06, P07, P08, P20, P21, P10, P12, P18, P14, P15, P11, P09.

**Dependencias:** P03 y P16 necesitan P04 (el modelo creado en SQL Server). P05 necesita los datos de Gold. P06 y P07 necesitan los CSV del caso.

---

## P01 · Pruebas de paridad Spark frente a DuckDB

**Estado actual:** confirmado en nuestra revisión con Python 3.11 y PySpark 3.5.3 (89 pasan). Falta guardar la salida desde tu equipo.

**Qué hacer:**
1. Crea un entorno con Python 3.11 (con 3.12 las pruebas de Spark se omiten o fallan en Windows). Instala `requirements.txt`, `requirements-spark.txt` y Java 17.
2. Desde la raíz del repositorio, ejecuta:
   - `python -m pytest tests/test_spark_paridad.py -v`
   - `python src/shared/spark/verificar_paridad_real.py`
3. Guarda ambas salidas.

**Criterio de cierre:** las pruebas de paridad pasan (sin omisiones) y el script imprime `PARIDAD COMPLETA`, con las cinco cifras y los nueve conteos por regla iguales a DuckDB.

**Evidencia:** `pytest_paridad.txt` y `verificar_paridad_real.txt`.

---

## P02 · Spark SQL igual a DuckDB en las consultas de venta

**Estado actual:** no confirmado. En Windows falla por falta de `HADOOP_HOME` con `winutils.exe`.

**Qué hacer:**
- Opción A, Windows: instala `winutils.exe` compatible con Hadoop 3 desde una fuente que confíes, define `HADOOP_HOME` y ejecuta `python -m pytest tests/test_sql_spark.py -v`.
- Opción B, Linux o WSL: crea el entorno ahí y ejecuta el mismo comando.
- Requisito: que exista `data/warehouse.duckdb` (lo genera `python scripts/cargar_datos.py --desde-cero`).

**Criterio de cierre:** la prueba pasa sin omitirse.

**Evidencia:** `pytest_sql_spark.txt`.

---

## P03 · T-SQL de venta neta y recompra en SQL Server

**Estado actual:** no ejecutado. Antes se afirmó "verificado por traducción mecánica", pero no hay ningún artefacto que lo respalde. Esa afirmación se retiró.

**Qué hacer:**
1. Instala SQL Server Developer (gratuito) o usa Docker con la imagen oficial de SQL Server.
2. Completa P04 primero: crea el modelo con `sqlserver/ddl_tsql.sql`.
3. Carga las tablas de Silver (clientes, pedidos, pagos) desde DuckDB: exporta a CSV con consultas sobre `data/warehouse.duckdb` y usa `BULK INSERT` o el asistente de importación.
4. Ejecuta `sqlserver/01_ventas_recompra.sql` completo.
5. Compara con las cifras de referencia.

**Criterio de cierre:**
- La consulta de venta neta mensual por canal devuelve 63 filas.
- La suma de la venta neta es 14.177.333.600.
- La recompra 2026 a 1, 3 y 6 meses es 26,1 %, 49,2 % y 57,1 %.

**Evidencia:** la salida de las consultas (exportada a CSV o captura), la versión de SQL Server (`SELECT @@VERSION`) y el `resultado.md`.

---

## P04 · DDL del modelo en SQL Server o Fabric Warehouse

**Estado actual:** no ejecutado.

**Qué hacer:**
1. Crea una base de datos vacía en SQL Server.
2. Ejecuta `sqlserver/ddl_tsql.sql` por lotes (el archivo usa `GO` como separador).
3. Revisa si algún lote falla. Si una clave foránea o una longitud de columna falla, anota el error exacto y no lo ocultes.

**Criterio de cierre:** el script se ejecuta sin errores. Si hay errores, quedan documentados y se corrigen en el repositorio con una nota.

**Evidencia:** el log completo de ejecución y el listado de tablas creadas (`SELECT name FROM sys.tables`).

---

## P05 · Medidas DAX en Power BI Desktop

**Estado actual:** no ejecutado. Los valores esperados salen de un cálculo en SQL.

**Qué hacer:**
1. Instala Power BI Desktop (gratuito, Windows).
2. Importa los datos de Gold y las tablas que necesitan las medidas. Ojo: el archivo `fabric/semantic_model/medidas.dax` espera una tabla `fact_pedido` (un pedido por fila, con `fecha_key`, `estado`, `valor_bruto`, `descuento`) y una `dim_fecha` con una columna `fecha` marcada como tabla de fechas. El almacén local no tiene `fact_pedido` ni `dim_fecha` tal cual: constrúyelas desde `silver_pedidos` y un calendario de 2025 a 2026, y documenta la construcción.
3. Crea la relación entre `fact_pedido[fecha_key]` y `dim_fecha[fecha_key]`.
4. Agrega la columna calculada `tiene_datos` y las medidas de `medidas.dax`.
5. Compara los cinco meses de la tabla de `docs/03_dax.md` (enero, febrero, marzo, junio y septiembre de 2026).
6. Compara también la variación anual de 2026 enero a septiembre: debe dar +98,9 % con la limitación de fechas, y +20,2 % sin ella.

**Criterio de cierre:** venta, pedidos, ticket y variación coinciden con la tabla de valores esperados (margen de redondeo de un punto porcentual).

**Evidencia:** captura de la tabla con las medidas y el archivo `.pbix` (sin datos de clientes; si contiene datos personales, no lo subas al repositorio).

---

## P06 · Notebook Delta en Fabric

**Estado actual:** no ejecutado. Incluye MERGE, DELETE e historial de Delta.

**Qué hacer:**
1. Crea un espacio de trabajo en Microsoft Fabric con la prueba gratuita o una capacidad disponible (verifica la oferta vigente).
2. Crea un Lakehouse y sube los cuatro CSV a `Files/andina/raw/`.
3. Importa `fabric/notebooks/andina_etl_spark.ipynb`, adjunta el Lakehouse y deja `PLATAFORMA = "fabric"` en la celda de configuración.
4. Ejecuta todas las celdas en orden.
5. Revisa la última celda de verificación.

**Criterio de cierre:** las cinco cifras de la celda de verificación dicen `OK` y ninguna celda falla. Si algo falla, anota la celda y el error.

**Evidencia:** captura de la celda de verificación y del historial de ejecución, y el mensaje de error completo si lo hubo.

---

## P07 · Notebook en Databricks

**Estado actual:** no ejecutado.

**Qué hacer:**
1. Usa una prueba o una edición gratuita de Databricks (verifica disponibilidad).
2. Crea un catálogo `andina`, un esquema `datos` y dos volúmenes, `raw` y `bronze`. Sube los CSV a `raw`.
3. Importa el mismo notebook y cambia `PLATAFORMA = "databricks"` en la celda de configuración.
4. Ejecuta todas las celdas y revisa la verificación.

**Criterio de cierre:** las cinco cifras coinciden y las rutas de volúmenes funcionan.

**Evidencia:** captura de la verificación y del historial de ejecución.

---

## P08 · Optimización de la consulta en SQL Server

**Estado actual:** no medido en SQL Server. El experimento se hizo en SQLite con datos sintéticos.

**Qué hacer:**
1. Usa SQL Server (P03) con datos de prueba. Si no tienes 50 millones de pedidos, usa 5 millones y documenta la escala.
2. Ejecuta la consulta original y la reescrita de `sqlserver/optimizacion/02_optimizacion.sql` con `SET STATISTICS TIME ON` y `SET STATISTICS IO ON`, y con el plan de ejecución real activado.
3. Quita la conversión de tipo del cruce con tickets y mide otra vez (la ablación).
4. Compara resultados: deben ser idénticos.

**Criterio de cierre:** tiempos y planes medidos en SQL Server, con la escala documentada.

**Evidencia:** los mensajes de estadísticas, los planes de ejecución (archivo `.sqlplan`) y una tabla con los tiempos.

---

## P09 · Política de retención y contrato del proveedor de IA

**Estado actual:** la llamada a la API se ejecutó con dos modelos, con un costo de unos USD 0,03. Falta confirmar la política de retención de datos del proveedor.

**Qué hacer:**
1. Lee la política de privacidad y de retención de datos del proveedor (DeepSeek) y, si existe, el contrato de uso comercial.
2. Confirma los nombres de los modelos que se usaron y su precio vigente en su página oficial.
3. Anota si los textos enviados se usan para entrenar modelos y cuánto tiempo se conservan.

**Criterio de cierre:** hay un párrafo con la política citada textualmente, con su fecha de consulta y enlace.

**Evidencia:** captura o PDF de la política, con fecha, y el texto citado en `resultado.md`.

---

## P10 · Revisión de las 34 etiquetas de referencia

**Estado actual:** las etiquetas las propuso la IA y nadie las ha validado.

**Qué hacer:**
1. Abre `src/shared/tickets_ia/datos/etiquetas_reales.csv` (34 descripciones, con su tipo asignado).
2. Para cada fila, decide si la etiqueta es correcta. Si no lo es, anota el tipo correcto. Usa la taxonomía de `src/shared/tickets_ia/taxonomia.py` y las distinciones de la documentación (por ejemplo, `pedido_no_llega` frente a `entrega_no_recibida`).
3. Guarda el resultado en `docs/evidencia/P10/etiquetas_revisadas.csv`, con una columna `revisor` (rol, no nombre) y una columna `cambio` (sí/no).
4. Cuenta cuántas cambiaste.

**Criterio de cierre:** las 34 filas revisadas, con el conteo de cambios.

**Evidencia:** el CSV revisado y el número de cambios en `resultado.md`. Después, reemplaza la frase "PENDIENTE DEL AUTOR" en `docs/07_clasificacion_ia.md`.

---

## P11 · Muestra de tickets reales etiquetada por personas

**Estado actual:** el caso no trae textos nuevos para medir la clasificación de forma independiente.

**Qué hacer:**
1. Obtén tickets reales de otra fuente (exportación del sistema de soporte), anonimizados: sin nombres, documentos, teléfonos ni correos. Si no es posible anonimizarlos, no los envíes a ninguna API externa.
2. Toma una muestra estratificada por tipo, de 100 a 200 tickets.
3. Dos personas etiquetan cada ticket por separado. Calcula el acuerdo (kappa) entre ellas.
4. Compara con el modelo solo si la política de P09 lo permite.

**Criterio de cierre:** muestra etiquetada, acuerdo entre anotadores calculado y, si aplica, exactitud del modelo con intervalo de confianza.

**Evidencia:** la muestra anonimizada, el cálculo del acuerdo y el resultado en `resultado.md`.

---

## P12 · Definición de venta neta firmada y dueños por dominio

**Estado actual:** es una decisión de negocio. Hay que definir si la venta incluye devoluciones y a qué fecha se atribuye.

**Qué hacer:**
1. Reúne a finanzas y comercial. Decidan: qué cuenta como venta, si las devoluciones restan, a qué fecha se atribuye (compra o entrega) y quién es el dueño de cada dominio (ventas, pagos, clientes).
2. Registra la decisión en un documento de una página, con firmas de los roles (no de nombres personales en el repositorio).
3. Si la decisión cambia algo del modelo, abre un cambio en el repositorio con `--recalcular-gold`.

**Criterio de cierre:** documento firmado por los roles, guardado como PDF.

**Evidencia:** el PDF firmado (sin datos personales) y una nota en `resultado.md`.

---

## P13 · Fecha de entrega: límite del 21 de octubre frente al 31 de octubre

**Estado actual:** el enunciado fija el límite el 21 de octubre de 2026. El README dice que la entrega es del 31 de octubre. No hay prórroga escrita en los archivos.

**Qué hacer:**
1. Revisa el correo o el canal donde recibiste la prueba.
2. Si hubo prórroga, pide confirmación escrita al reclutador. Si no hubo, decide cómo presentarlo.

**Criterio de cierre:** confirmación escrita, citada en el README.

**Evidencia:** captura del correo de confirmación (sin datos personales de terceros).

---

## P14 · Licencias de Power BI Pro bajo F64 y costos de Fabric y Databricks

**Estado actual:** hipótesis sin cotización.

**Qué hacer:**
1. Revisa la documentación oficial de licencias de Power BI y de capacidades de Fabric. Confirma si quien consume informes sin capacidad F64 necesita Power BI Pro.
2. Pide cotización formal a Microsoft (o a un partner) para la capacidad que propones, y a Databricks para el consumo estimado.
3. Anota fecha, moneda y supuestos de cada cotización.

**Criterio de cierre:** dos cotizaciones con supuestos, o la confirmación de la regla de licencias con enlace oficial.

**Evidencia:** PDF de cotizaciones o captura de la página oficial con fecha.

---

## P15 · Revisión visual de la presentación en un navegador

**Estado actual:** la sintaxis de los diagramas se validó con Mermaid 10.9.1. La maquetación se revisó solo en escritorio, con capturas de Microsoft Edge en modo sin cabeza. No se revisó en teléfono.

**Qué hacer:**
1. Abre `docs/presentacion_entrega.html` en Chrome o Edge (necesitas conexión para cargar las fuentes y Mermaid).
2. Recorre todas las pestañas en escritorio.
3. Abre las herramientas de desarrollador, activa la vista de teléfono (unos 400 px) y recorre las pestañas otra vez.
4. Anota lo que se corte, se superponga o no se lea.

**Criterio de cierre:** ninguna pestaña con texto cortado ni diagramas superpuestos en escritorio, y en teléfono sin desbordamiento horizontal de la página.

**Evidencia:** capturas de las pestañas con problemas y la lista de correcciones pendientes.

---

## P16 · Reporte de ventas contra SQL Server real

**Estado actual:** las pruebas usan una base en memoria, no un servidor.

**Qué hacer:**
1. Completa P03 y P04 (la tabla `gold.fact_venta_neta_diaria` y `gold.dim_canal` deben existir).
2. Crea un usuario de solo lectura en SQL Server.
3. Define la cadena de conexión en una variable de entorno de tu equipo, nunca en un archivo del repositorio. Ten instalado ODBC Driver 18 for SQL Server y `pyodbc`.
4. Ejecuta `python src/shared/reporte_ventas.py` para un día con ventas y compara con el valor calculado en DuckDB para ese mismo día.

**Criterio de cierre:** el reporte imprime el mismo total y el mismo número de pedidos que DuckDB para el día elegido, en los tres canales.

**Evidencia:** la salida del reporte, redactada (sin la cadena de conexión), y el cálculo de referencia.

---

## P17 · Rotación de credenciales expuestas

**Estado actual:** urgente. Dos credenciales quedaron expuestas.

**Qué hacer:**
1. Clave de DeepSeek: genera una clave nueva en la consola del proveedor y revoca la anterior. Actualiza `.env.local` con la nueva. **No la pegues en ningún chat.**
2. Contraseña de administrador del pull request: cámbiala en el servidor. Revisa el historial del código; si el repositorio se sube a un servidor, borra el historial que la contenga o trata la contraseña como comprometida.
3. Revisa que `.env.local` no esté en ningún lugar que se suba a git (el `.gitignore` ya lo excluye, pero solo tiene efecto cuando el repositorio sea git).

**Criterio de cierre:** las dos credenciales anteriores ya no funcionan, y la nueva está solo en `.env.local` o en un gestor de secretos.

**Evidencia:** confirmación de revocación (captura sin mostrar la clave) y la fecha.

---

## P18 · Umbrales de cuarentena y de volumen

**Estado actual:** el método está propuesto, pero los números no existen todavía. Con un solo archivo no hay histórico de treinta días.

**Qué hacer:**
1. Para calcular un umbral necesitas cargas diarias reales durante al menos treinta días: la tasa de registros en cuarentena por carga y el volumen de pedidos por día.
2. Con esos datos, calcula el promedio y la desviación estándar, y propón un umbral (por ejemplo, promedio más dos desviaciones).
3. La dirección y el dueño del dato aprueban el umbral.

**Criterio de cierre:** serie de treinta días, cálculo y aprobación escrita.

**Evidencia:** la serie y el cálculo, y la aprobación.

---

## P19 · Salidas guardadas de las ejecuciones declaradas

**Estado actual:** el repositorio no conserva salidas de Spark SQL ni de las reglas en PySpark. Hay que dejarlas guardadas.

**Qué hacer:** ejecuta y guarda la salida de cada comando de este documento, con la fecha. Como mínimo:
- `python -m pytest -v > docs/evidencia/P19/pytest_completo.txt`
- `python scripts/cargar_datos.py --desde-cero > docs/evidencia/P19/carga_desde_cero.txt`
- `python scripts/cargar_datos.py > docs/evidencia/P19/carga_segunda.txt`

**Criterio de cierre:** los tres archivos existen y muestran `CARGA CORRECTA` y el resultado de las pruebas.

**Evidencia:** los archivos de salida.

---

## P20 · Cifra mensual de APP

**Estado actual:** la afirmación "APP crece" se retiró del texto porque no tiene cifra en la entrega.

**Qué hacer:** con `data/warehouse.duckdb`, ejecuta una consulta que sume la venta neta por mes y canal, y compara APP entre meses. Puedes usar:
`SELECT date_trunc('month', fecha) AS mes, canal, sum(venta_neta) AS venta FROM gold_venta_neta_diaria GROUP BY 1, 2 ORDER BY 1, 2;`

**Criterio de cierre:** tabla mensual de APP, y si la afirmación se restituye, con la cifra.

**Evidencia:** la tabla exportada y la decisión en `resultado.md`.

---

## P21 · Prueba de la caída de TIENDA con datos de 2025 (recomendada)

**Estado actual:** la caída de TIENDA entre junio y septiembre de 2026 es un hallazgo. No sabemos si es estacional. Los datos de 2025 permiten comprobarlo.

**Qué hacer:** con la misma consulta de P20, compara TIENDA de junio a septiembre de 2025 contra junio a septiembre de 2026.

**Criterio de cierre:** la comparación con las cifras, y una conclusión que diga si la caída es o no es estacional según estos datos.

**Evidencia:** la tabla de comparación.

---

## Plantilla de cierre de un pendiente

Cuando termines un pendiente, actualiza su estado en `docs/presentacion_entrega.html` (pestaña Pendientes) y en este documento, con la fecha y la ruta de la evidencia.
