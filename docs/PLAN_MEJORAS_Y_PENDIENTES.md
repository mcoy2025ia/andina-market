# Andina Market — Plan de mejoras y pendientes

**Fecha de corte:** 1 de noviembre de 2026, hora de Colombia.  
**Objetivo:** completar la entrega técnica y preparar, por etapas, su evolución a un servicio de datos confiable.  
**Alcance de este archivo:** diagnóstico y plan de trabajo. Crear este documento no significa que sus tareas ya se hayan implementado.

## 1. Qué tenemos y qué falta realmente

La solución tiene una base local funcional: Bronze en Parquet, validación de clientes/pedidos/pagos, cuarentena, escrituras idempotentes, procesamiento incremental de pagos y venta neta diaria en DuckDB. También existen SQL en varios dialectos, reglas PySpark, un notebook Delta, DDL, medidas DAX, una revisión de código y un experimento de clasificación de tickets.

El salto pendiente más importante es **conectar esa base con el modelo y la operación de la plataforma destino**. El ETL local no carga por sí mismo el esquema estrella que esperan DAX y el reporte ODBC. Escribir DDL, medidas o un notebook no demuestra que funcionen juntos en SQL Server, Power BI, Fabric o Databricks.

### Evidencia disponible al corte

| Elemento | Estado que podemos sostener | Límite |
|---|---|---|
| Pruebas locales | En esta revisión: **85 aprobadas, 2 omitidas**, en 10,52 s | No equivalen a validar las pruebas omitidas ni motores externos |
| Datos de venta mensual | Consulta de solo lectura a Gold: **63 filas**, 21 meses × 3 canales | No se reconstruyó toda la carga durante esta revisión |
| APP, junio–septiembre de 2026 | COP 376.510.600 → 448.880.300; **+19,22 %** | Describe ese intervalo, no una tendencia perpetua |
| TIENDA, junio–septiembre de 2026 | COP 217.573.400 → 105.808.200; **−51,37 %** | No demuestra una causa |
| TIENDA, junio–septiembre de 2025 | COP 113.766.000 → 181.788.300; **+59,79 %** | Dos años no bastan para concluir si existe o no estacionalidad |
| Presentación ejecutiva | Rediseñada: 16 capítulos y un diagnóstico de 33 asuntos | No cierra automáticamente los pendientes del sistema |
| Presentación por puntos | Creada: 13 pestañas, una por punto/subpunto evaluado | El estado de validación se indica en cada pestaña |
| QA de las presentaciones | Edge sin interfaz, escritorio y móvil: sin errores JS ni desbordamiento horizontal en las secciones recorridas | No es una auditoría completa de accesibilidad o de todos los navegadores |
| Reglas Spark y recálculo independiente | Ejecuciones previas declaradas en la documentación | Falta consolidar salidas y reconciliar estados contradictorios |
| Clasificador LLM | Hay resultados guardados de ejecuciones previas | Referencias humanas y generalización real todavía pendientes |
| SQL Server, DAX y Delta cloud | Código entregado | No se validaron en sus plataformas durante esta revisión |

Evidencias: [validación local](evidencia/presentacion/validacion_local.txt), [ventas mensuales](evidencia/presentacion/ventas_mensuales.csv), [QA ejecutivo](evidencia/presentacion/qa_navegador.json) y [QA por puntos](evidencia/presentacion/qa_resolucion.json).

### Cómo leer las prioridades

- **P0 — Cierre de entrega:** coherencia, evidencia y riesgos concretos que pueden debilitar la sustentación.
- **P1 — Integración funcional:** completar o robustecer capacidades de la solución.
- **P2 — Operación:** requisitos antes de usar el proyecto como un servicio de producción.
- **P3 — Evolución:** optimizaciones o ampliaciones justificadas por uso y volumen.

Estas prioridades no significan que la prueba original exija desplegar todo en producción. Por ejemplo, el enunciado pide escribir DAX y proponer arquitectura; ejecutarlos en destino fortalece la evidencia, pero no convierte toda la arquitectura propuesta en un entregable ya solicitado.

## 2. Reparto del trabajo

| Grupo | Qué podemos hacer | Qué no reemplaza la IA |
|---|---|---|
| **A — Con IA desde ya** | Leer y modificar código/documentación, crear pruebas, automatizar verificaciones, preparar scripts y trabajar con datos locales autorizados | Decisiones de negocio, accesos que no existen o resultados de motores que no se ejecutaron |
| **U — Tu intervención** | Confirmar contexto, aprobar definiciones, revisar etiquetas, aportar accesos y presupuesto, validar aceptación | La IA puede preparar todo el material, pero no debe inventar tu decisión ni tu revisión |
| **E — Ejecución con entorno habilitado** | La IA puede preparar y, con herramientas/acceso autorizado, ejecutar el trabajo técnico | Necesita el entorno y su autorización; no es obligatorio que tú ejecutes manualmente cada comando |

**Se puede avanzar en el grupo A sin esperar a contratar nube ni a completar el grupo U.** Cuando una tarea depende de una definición pendiente, se conserva el contrato del caso y se deja la alternativa documentada.

## 3. Grupo A — Mejoras que podemos realizar ya con IA

### A01 · Unificar estados, cifras y declaración de asistencia — P0

**Observación:** README y lectura SQL declaran Spark SQL ejecutado; P02 sigue como no confirmado. Hay conteos de 85, 89 y 90 pruebas en distintos documentos. La fecha del README no coincide con el límite del enunciado. El inventario anterior de pendientes quedó desactualizado frente a las nuevas presentaciones.

**Trabajo:**

1. Crear una matriz única por artefacto: escrito, probado localmente, probado en destino, pendiente o no aplicable.
2. Asociar cada ejecución con fecha, entorno, comando y salida.
3. Actualizar README, README_ETL, arquitectura, pendientes y presentaciones desde esa matriz.
4. Distinguir la fecha de preparación/revisión de la fecha de entrega aceptada.
5. Actualizar la declaración de asistencia: Claude en la solución previa y Codex en revisión y presentaciones, según corresponda.

**Archivos:** `README.md`, `README_ETL.md`, `docs/04_arquitectura.html`, `docs/PENDIENTES_EJECUCION.md`, ambas presentaciones.  
**Dependencia:** U01 para resolver la fecha administrativa; mientras tanto se registra la discrepancia.  
**Cierre:** ninguna afirmación contradictoria o ejecución sin evidencia identificable. El PDF de arquitectura se regenera si cambia su fuente.

### A02 · Crear un paquete reproducible de evidencias — P0

**Observación:** la salida nueva de pytest está resumida, pero falta un expediente completo y uniforme de las ejecuciones del proyecto.

**Trabajo:** crear un comando de verificación que registre versiones, comando, código de salida, pruebas aprobadas/omitidas y motivo; ejecutar carga, segunda carga y recálculo en **rutas temporales aisladas**. Comparar totales y filas. Guardar salidas sin datos personales ni secretos. No usar `--desde-cero` sobre la base de trabajo para una verificación rutinaria.

**Entregables:** script de verificación, manifiesto de entorno y carpeta `docs/evidencia/<fecha>/`.  
**Cierre:** un tercero puede reconstruir el caso con los CSV autorizados; la segunda carga no inserta ni actualiza; los totales coinciden y las omisiones quedan explicadas.

### A03 · Empaquetar la entrega y preparar control de versiones — P0

**Observación:** en la carpeta inspeccionada no se encontró `.git`; existen entornos Python, datos y resultados que no deben incluirse indiscriminadamente en la entrega.

**Trabajo:** preparar una lista explícita de archivos entregables, verificar exclusiones, crear un `.env.example` sin valores reales y automatizar un ZIP limpio. Si se elige Git, inicializar y organizar el repositorio local dentro del trabajo autorizado, sin publicar ni subir datos automáticamente.

**Cierre:** paquete con README, código, dependencias, pruebas y documentación; sin entornos virtuales, claves, bases o CSV personales. Registrar versión o hash del paquete.  
**Dependencia:** U02 para destino y modalidad final. El `.gitignore` no demuestra que nunca haya habido una exposición ni protege un ZIP armado manualmente.

### A04 · Robustecer el SQL para meses sin venta — P1

**Observación:** `LAG` opera sobre meses presentes. Si falta un mes de un canal, el anterior podría no ser el mes calendario inmediato. Con los datos actuales existen los 21 meses para los tres canales.

**Trabajo:** construir calendario mes × canal; enlazar agregados; definir cómo mostrar ausencia de venta; calcular variación respecto del mes contiguo; tratar denominadores cero y primer mes. Replicar la lógica en los dialectos y la plantilla Spark.

**Pruebas:** canal sin un mes intermedio, primer mes, mes previo cero y mes sin pedidos entregados.  
**Archivos:** `duckdb/`, `sqlserver/`, `fabric/sql/`, `databricks/sql/`, `src/shared/spark/sql/`.  
**Cierre:** resultados iguales al caso actual y correctos en los nuevos bordes. T-SQL sigue pendiente de E02 hasta ejecutarlo allí.

### A05 · Crear pruebas de contrato entre indicadores — P1

**Observación:** la definición de venta se repite en reglas, Gold, SQL, DAX y documentación. Esa repetición permite divergencias futuras.

**Trabajo:** crear un conjunto pequeño de referencia con entregados, devueltos, cancelados, descuentos, clientes duplicados y fechas límite. Especificar resultados esperados por día, mes, canal, ticket y cohorte. Usar esas mismas expectativas en pruebas locales y exportarlas para validar los otros motores.

**Cierre:** una modificación que cambie la definición en una sola capa produce una diferencia visible. Las medidas DAX no se consideran probadas por inspeccionar su texto: necesitan E03.

### A06 · Construir el puente Silver → esquema estrella — P1, integración crítica

**Observación:** DuckDB genera `gold_venta_neta_diaria`. DAX espera `fact_pedido`; el reporte consulta `gold.fact_venta_neta_diaria` y `gold.dim_canal`. El DDL define estructuras, pero no resuelve su carga.

**Trabajo:**

1. Definir el mapeo entre Silver y dimensiones/hechos del DDL.
2. Implementar calendario, claves y miembro de cliente desconocido según el contrato.
3. Cargar dimensiones antes que hechos; preservar unicidad y grano de un pedido por fila.
4. Cargar el agregado diario con sus claves de dimensiones.
5. Diseñar recarga e incremental sin duplicados y conciliaciones automáticas.
6. Separar los scripts específicos de SQL Server de cualquier adaptación necesaria para Fabric Warehouse; no asumir compatibilidad total por compartir T-SQL.

**Entregables:** scripts de carga, mapeo y pruebas locales de transformaciones.  
**Cierre:** importes y pedidos del modelo destino concilian con Silver y Gold; claves sin huérfanos no explicados. La validación del destino se completa en E01.

### A07 · Formalizar contratos de entrada y errores de esquema — P1

**Observación:** el proceso presupone nombres de columnas y materializa snapshots en pandas. Falta un contrato explícito que distinga un archivo estructuralmente inválido de una fila inválida.

**Trabajo:** validar columnas obligatorias, claves, codificación y formatos antes de transformar; definir tratamiento de columnas extra; documentar tipos esperados; registrar errores estructurales comprensibles; impedir publicación si falta una columna esencial.

**Pruebas:** columna faltante, columna adicional, archivo vacío, formato de fecha inválido y cambio de tipo.  
**Cierre:** los errores estructurales no se convierten silenciosamente en cifras parciales ni en trazas difíciles de interpretar.

### A08 · Definir precisión monetaria y catálogos — P1

**Observación:** los importes se convierten a enteros. Falta explicitar qué debe ocurrir si llegan fracciones. La categoría se limpia como texto, sin un catálogo gobernado equivalente al mapa de canales.

**Trabajo inmediato:** documentar el comportamiento actual, añadir casos con decimales y categorías nuevas, preparar alternativas de rechazo o precisión decimal. Conservar las cifras del caso mientras se decide.

**Dependencia:** U03 para escoger precisión, redondeo y tratamiento de categorías desconocidas.  
**Cierre:** no hay truncamiento monetario no explicado; una categoría nueva tiene un tratamiento definido y probado.

### A09 · Revalidar relaciones y gestionar incidencias — P1

**Observación:** `flag_cliente_desconocido` se actualiza al escribir el pedido. Si llega el cliente posteriormente y el pedido no cambia, puede quedar desactualizado. La cuarentena conserva historia, pero falta una vista operativa de resolución.

**Trabajo:** revalidar pedidos afectados por cambios del maestro; separar historial de incidencias de estado actual; incorporar estado abierto/resuelto, última revisión y motivo de resolución; conservar el registro original.

**Pruebas:** cliente tardío, pedido corregido, pago recuperado, nueva regla y misma incidencia repetida.  
**Cierre:** los indicadores de calidad reflejan la situación vigente sin borrar la trazabilidad histórica.

### A10 · Diseñar reconciliación histórica y borrados — P1

**Observación:** un pedido borrado de la fuente puede permanecer en Silver; una corrección antigua de un pago puede quedar fuera del lookback.

**Trabajo inmediato:** implementar un modo de reconciliación completa en una base aislada; comparar fuente y destino; detectar candidatos a baja y cambios fuera de ventana; producir un informe antes de aplicar una eliminación. Preparar contrato de `updated_at` y marcas de borrado.

**Dependencia:** U03/U04 para confirmar si el archivo es snapshot completo o parcial y qué significa una ausencia.  
**Cierre:** pruebas de corrección tardía y borrado explícito; no borrar registros simplemente porque faltan en una fuente de alcance desconocido.

### A11 · Integrar tickets de soporte al flujo — P1/P2

**Observación:** los tickets no entran al ETL. Los 99 cierres anteriores a creación y los 59 tickets cerrados sin fecha solo tienen tratamiento propuesto.

**Trabajo:** añadir Bronze/Silver de tickets, trazabilidad y reglas; conservar el ticket y marcar incoherencias; evitar promediar duraciones negativas; enlazar cliente/pedido; permitir asociar la clasificación mediante una clave estable y una versión del clasificador.

**Dependencia:** U03 para criterios de SLA y tratamiento de fechas.  
**Cierre:** carga idempotente de soporte, conteos reconciliados, métricas de resolución que no mezclen casos válidos e inválidos. No es necesario para afirmar que el ETL de pedidos/pagos satisface su alcance original.

### A12 · Robustecer el cliente LLM sin consumir API real — P1

**Observación:** `interpretar` admite confianza numérica sin limitarla a `[0,1]`; el bucle gestiona respuestas inválidas, pero no configura una política propia de recuperación de errores de transporte. El SDK puede tener sus propios reintentos: deben considerarse para evitar multiplicarlos.

**Trabajo:** validar JSON, tipos, valores finitos y rango de confianza; decidir qué hacer si falta confianza; configurar timeout y presupuesto total de intentos; distinguir errores transitorios de permanentes; probar caché; registrar modelo/prompt/versión. Preparar cola de revisión y fallo explícito, sin tratar la confianza declarada por el modelo como una probabilidad calibrada.

**Pruebas simuladas:** JSON vacío, lista en vez de objeto, etiqueta desconocida, confianza negativa/superior a uno/NaN, timeout, 429 y agotamiento de intentos.  
**Cierre:** ejecución determinista de las pruebas sin red ni gasto; resultado fallido identificable y contadores consistentes. Archivos: `src/shared/tickets_ia/llm.py`, `tests/test_tickets_ia.py`.

### A13 · Preparar evaluación humana y una evaluación reservada — P0/P1

**Trabajo:** crear una plantilla de revisión de las 34 etiquetas, guía de taxonomía con ejemplos ambiguos, formato para dos anotadores y herramienta de discrepancias. Preparar partición de desarrollo/evaluación que evite duplicados y paráfrasis cercanas entre grupos; calcular F1, matriz, consistencia e intervalos apropiados.

**Dependencia:** U05 para revisar etiquetas; U06 para conseguir tickets reales nuevos.  
**Cierre de la parte IA:** plantillas y evaluador listos con pruebas. La validez humana del conjunto no se cierra generando más etiquetas con otro LLM.

### A14 · Completar el reporte con una salida verificable — P1/P2

**Observación:** `enviar_reporte` calcula y registra resultados; el envío del correo sigue como TODO.

**Trabajo inmediato:** generar HTML/archivo del reporte, fecha de corte y estado de validación; separar cálculo, renderizado y entrega; crear transporte simulado y modo de vista previa; impedir envío si no pasó la conciliación. Añadir identificador de reporte para evitar duplicados al reintentar.

**Dependencia:** U07 para destinatarios, horario y canal; E02 para ODBC.  
**Cierre:** reporte verificable en modo local, error observable y entrega idempotente probada con un receptor simulado. Un envío real requiere instrucción explícita y destinatarios confirmados.

### A15 · Crear CI local y configuración para CI remoto — P1/P2

**Trabajo:** fijar comandos de instalación y pruebas, validación de SQL/configuración y generación de artefactos; separar pruebas locales de integración Spark/SQL Server; comprobar que las omisiones esperadas no oculten fallos. Preparar workflow para el proveedor elegido y verificación de archivos generados.

**Dependencia:** U02 para alojamiento y E05 para ejecución remota.  
**Cierre local:** un comando reproduce los chequeos y falla ante una regresión real.  
**Cierre remoto:** un PR correcto pasa y uno deliberadamente defectuoso se bloquea. Un archivo YAML no prueba que la protección de ramas esté activada.

### A16 · Implementar compuertas configurables de publicación — P2

**Observación:** el proceso registra calidad y mantiene atomicidad local, pero no implementa los umbrales y bloqueo de publicación descritos en la arquitectura.

**Trabajo:** separar carga, validación y publicación; comparar conteos, frescura y totales; permitir reglas configurables; conservar la última versión validada; generar un resultado de ejecución consumible por un sistema de alertas. Probar una discrepancia que impida publicar.

**Dependencia:** U08 para umbrales reales y tolerancias. Para desarrollar, usar valores sintéticos marcados como prueba.  
**Cierre:** una carga incompleta no se distribuye como oficial y deja evidencia de qué condición falló.

### A17 · Preparar recuperación, concurrencia y observabilidad — P2

**Trabajo:** diseñar exclusión de corridas o coordinación por lote; configurar reintentos; estructurar logs con `run_id`, etapa, estado y duración; redactar runbook de fallos; preparar pruebas de interrupción entre etapas y plan de restauración. En Delta, separar la recuperación multitabla de las garantías de una tabla individual.

**Dependencia:** U08/U09 para objetivos de servicio; E04/E05 para pruebas en nube.  
**Cierre local:** corridas concurrentes o fallidas no generan publicación parcial ni estados ambiguos.  
**Límite:** `git revert` revierte código; no revierte automáticamente datos, esquemas o modelos publicados.

### A18 · Completar material de sustentación — P0

**Trabajo:** mantener una pestaña por punto, enlazar archivos y evidencias, preparar un guion ejecutivo de diez minutos y ensayar cambios pequeños: canal nuevo, regla de descuento, atribución de fecha o ventana de recompra. Crear una copia de práctica y documentar qué archivos cambian por cada decisión.

**Cierre:** puedes localizar, explicar y modificar cada pieza; el cambio en vivo pasa las pruebas relevantes y actualiza los resultados esperados. La IA puede hacer de evaluador y señalar inconsistencias; no sustituye tu capacidad de defender el código.

## 4. Grupo U — Lo que necesitas decidir, revisar o habilitar tú

### U01 · Confirmar fecha y modalidad aceptadas — P0

**Por qué tú:** el enunciado fija el 21 de octubre y el README declara el 31. No hay evidencia de prórroga en los archivos revisados.

**Acción:** revisar tu citación/correo y confirmar fecha efectiva, canal de entrega y formato aceptado.  
**La IA prepara:** una lista de inconsistencias y el texto documental corregido.  
**Cierre:** confirmación verificable o explicación explícita de la discrepancia. No inventar una prórroga.

### U02 · Elegir destino de entrega y habilitar acceso — P0/P1

**Acción:** decidir ZIP o repositorio y, si aplica, proveedor, organización y visibilidad. Habilitar acceso por la conexión autorizada.  
**La IA prepara:** paquete limpio, estructura de repositorio, workflow y descripción de entrega.  
**Cierre:** destino elegido y permisos disponibles. La publicación no se deduce de haber pedido crear este plan.

### U03 · Ratificar el contrato de negocio — P1

**Decisiones concretas:**

1. Para el caso se mantiene bruto − descuento de ENTREGADO, por `fecha_pedido`.
2. Para operación real: qué ocurre con devoluciones posteriores y reembolsos, sin confundir venta con recaudo.
3. Precisión monetaria y política de fracciones/redondeo.
4. Canales/categorías permitidos y tratamiento de nuevos valores.
5. Fechas de corte, zona horaria y definición de día cerrado.
6. Recompra: cohorte de registro, ventana desde primera compra, denominador y madurez.
7. Tratamiento de tickets con fechas incoherentes y cálculo de SLA.

**La IA prepara:** contrato de una página, ejemplos y pruebas de impacto.  
**Cierre:** decisiones escritas. Si el proyecto pasa a una organización real, deben aceptarlas los dueños de negocio; tú no necesitas inventar firmas para una empresa ficticia.

### U04 · Confirmar semántica y disponibilidad de fuentes — P1

**Acción:** confirmar si cada archivo es snapshot completo o incremento, si existe `updated_at`, cómo se comunican borrados y qué retrasos/correcciones son posibles. Para un caso sin acceso a sistemas reales, documentar estas condiciones como supuestos.

**La IA prepara:** cuestionario técnico y adaptadores de ingesta.  
**Cierre:** contrato de extracción suficiente para implementar bajas y reconciliación sin eliminar información válida.

### U05 · Revisar las 34 etiquetas de referencia — P0 para sostener evaluación humana

**Acción:** leer cada descripción y aceptar o corregir su tipo; marcar casos ambiguos y explicar por qué. Prestar atención a diferencias como pedido pendiente frente a entrega declarada pero no recibida.

**La IA prepara:** tabla de revisión, guía y resumen de cambios.  
**Cierre:** 34 decisiones revisadas, cambios registrados y fecha de revisión. No declarar “validación humana” si solo otra IA revisó las etiquetas.

### U06 · Conseguir muestra real independiente — P2 para decidir uso productivo de IA

**Acción:** obtener, si existe acceso autorizado, tickets nuevos representativos y revisores de negocio. No reutilizar los mismos 34 textos ni inventar que el conjunto sintético es una muestra real.

**La IA prepara:** muestreo, separación de conjuntos, evaluación y análisis de errores.  
**Cierre:** muestra reservada con procedencia y etiquetas humanas. Si no hay datos disponibles, el estado correcto es limitado/no evaluable con el caso actual.

### U07 · Confirmar entrega del reporte — P2

**Acción:** definir quién lo recibe, por qué canal, a qué hora, con qué período y qué mensaje recibe cuando no hay datos validados. Autorizar por separado cualquier envío real.

**La IA prepara:** vista previa, plantillas, transporte y pruebas simuladas.  
**Cierre:** especificación y destinatarios confirmados; integración validada sin envíos involuntarios.

### U08 · Aprobar calidad y objetivos operativos — P2

**Acción:** acordar frescura, horarios, tolerancia de conciliación, umbrales de calidad, responsables y escalamiento. Aportar historial de cargas reales para calibrar volumen y cuarentena; treinta días es un punto de partida del plan anterior, no garantía estadística suficiente para todos los patrones.

**La IA prepara:** análisis de línea base, simulaciones y configuración.  
**Cierre:** criterios aceptados y un ejemplo claro de cuándo se publica, cuándo se retiene y quién actúa. No usar umbrales arbitrarios como si fueran calibrados.

### U09 · Habilitar entorno, presupuesto y políticas — P1/P2

**Acción:** elegir el destino que se validará primero; facilitar acceso seguro a SQL Server/Power BI y, si corresponde, un workspace de Fabric o Databricks. Definir límite de consumo. Confirmar requisitos de permisos, retención, respaldo, RPO/RTO y uso de proveedor de IA con los responsables correspondientes.

**La IA prepara:** lista mínima de recursos, scripts, estimación basada en carga y matriz de permisos. También puede investigar condiciones vigentes cuando se aborde esa tarea.  
**Cierre:** entorno utilizable y alcance autorizado. No es necesario habilitar ambas nubes para resolver el caso; validar una no demuestra paridad con la otra.

### U10 · Confirmar acciones sobre credenciales señaladas — P0, según aplicabilidad

**Observación:** el documento previo declara exposición de una clave de DeepSeek. Esta revisión no inspeccionó la clave ni verificó su revocación. La contraseña del PR aparece en el enunciado: no se puede asumir que corresponda a un servidor real.

**Acción:** si la clave expuesta era real, revocarla y sustituirla desde el proveedor; confirmar si la contraseña del ejemplo se utilizó en algún sistema real y actuar solo en ese caso. No pegar valores de secretos en el chat o en las evidencias.

**La IA prepara:** configuración sin secretos y comprobaciones de exclusión/escaneo con valores redactados.  
**Cierre:** confirmación de revocación cuando aplique, o registro de no aplicabilidad del ejemplo. No marcar una credencial como rotada porque exista `.gitignore`.

## 5. Grupo E — Validaciones que podemos ejecutar con IA cuando exista el entorno

### E01 · DDL y carga del modelo en el destino elegido — P1

- **Necesita:** A06 + U09.
- **Ejecución:** crear estructuras en un entorno de prueba, cargar dimensiones/hechos, revisar restricciones e índices y conciliar con DuckDB.
- **Cierre:** clientes, pedidos y pagos concuerdan con sus referencias; venta total COP 14.177.333.600 y 16.855 pedidos entregados, siempre que no cambien datos/reglas; diferencias documentadas por grano.
- **Evidencia:** versión del motor, scripts, resultados y consultas de conciliación. Separar SQL Server y Fabric Warehouse si ambos se declaran soportados.

### E02 · T-SQL y reporte ODBC — P1

- **Necesita:** E01; driver y cliente Python para ODBC disponibles.
- **Ejecución:** correr ventas y cohortes; comparar resultados por fila con el motor local; ejecutar reporte para un día cerrado y los tres canales con permisos de lectura.
- **Cierre:** mismas cifras, denominadores y manejo de vacíos; consulta parametrizada y conexión real comprobadas.
- **Evidencia:** salidas sin cadenas de conexión y comparación de resultados.

### E03 · DAX en Power BI — P1

- **Necesita:** modelo cargado, calendario continuo y relaciones verificadas.
- **Ejecución:** importar/conectar el modelo, instalar medidas y probar filtros por mes, año, canal y ausencia de pedidos.
- **Referencias:** enero 2026 COP 948.592.900; septiembre COP 795.114.800; enero–septiembre 2026 COP 7.739.061.400; base comparable 2025 COP 3.891.305.400; variación aproximada +98,88 %.
- **Cierre:** valores esperados coinciden y 2025 sin año previo devuelve vacío; evitar comparar nueve meses con doce.
- **Evidencia:** modelo versionable, consultas/capturas con contexto de filtro y resultados.

### E04 · Spark local y Delta en nube — P1/P2

- **Necesita:** entorno compatible para Spark y, para cloud, U09.
- **Ejecución local:** pruebas de paridad y Spark SQL; registrar versiones y motivos de omisión. La IA puede preparar el entorno local si las herramientas disponibles lo permiten.
- **Ejecución cloud:** primera y segunda carga, cambios de pedido, pagos tardíos, retiradas, MERGE/DELETE, historial y recuperación tras fallo.
- **Cierre:** paridad de reglas y totales; segunda corrida sin duplicar; recuperación sin publicar resultados parciales. No extrapolar una ejecución de Fabric a Databricks.
- **Evidencia:** logs de motor y notebook con parámetros/rutas redactadas cuando corresponda.

### E05 · Operación y despliegue — P2

- **Necesita:** A15–A17 + U08/U09.
- **Ejecución:** CI remoto, promoción entre ambientes, secretos, permisos, programación, compuertas, alertas y restauración.
- **Cierre:** un cambio defectuoso queda bloqueado; una carga incompleta no se publica; una alerta llega al canal autorizado; una restauración cumple los objetivos acordados.
- **Evidencia:** ejecución de pruebas de incidente y recuperación. Preparar la prueba de alertas no autoriza por sí solo contactar destinatarios reales.

### E06 · Benchmark representativo de optimización — P1 para evidencia de rendimiento

- **Necesita:** SQL Server de prueba con recursos y volumen autorizados.
- **Ejecución:** comparar original y reescritura con equivalencia de resultados, plan real, IO y CPU; variar distribución y parámetros; medir impacto de índices en cargas. Resolver criterio de desempate del último ticket.
- **Cierre:** mejora demostrada en ese entorno y explicación del plan. Si no se prueban 50 millones, declarar el volumen real y no extrapolar tiempos como una medición.
- **Evidencia:** scripts reproducibles, planes y tabla de mediciones, incluidos casos que no mejoren.

## 6. Orden recomendado de ejecución

### Etapa 1 — Dejar la entrega coherente y defendible

**IA:** A01, A02, A03, A13 y A18.  
**Tú:** U01, U02, U05 y U10 cuando aplique.  
**Resultado:** entrega trazable, paquete limpio, estados honestos y etiquetas revisadas. Puede completarse sin desplegar nube.

### Etapa 2 — Robustecer el núcleo sin cambiar el negocio por sorpresa

**IA:** A04, A05, A07, A09 y A12; diagnóstico y opciones de A08/A10.  
**Tú:** U03 y U04.  
**Resultado:** bordes y errores controlados; contratos claros; correcciones tardías y cambios de maestro con tratamiento definido.

### Etapa 3 — Cerrar la integración analítica

**IA:** A06 y preparación de A14.  
**Tú:** U09; U07 si se incorpora distribución.  
**Con entorno:** E01, E02, E03 y parte local de E04.  
**Resultado:** la misma cifra comprobada en el modelo destino, SQL, reporte y DAX.

### Etapa 4 — Pasar a operación controlada

**IA:** A11, A15, A16 y A17, según alcance aceptado.  
**Tú:** U07, U08 y políticas de U09.  
**Con entorno:** E04 cloud y E05.  
**Resultado:** servicio con publicación validada, responsables y recuperación probada.

### Etapa 5 — Demostrar beneficio a mayor escala

**Trabajo conjunto:** E06 y evaluación real de IA con U06.  
**Resultado:** decisiones de optimización y automatización sustentadas en desempeño, calidad y costo medidos.

**Estimaciones:** el orden anterior expresa dependencias, no plazos prometidos. El esfuerzo debe estimarse por bloque una vez confirmados destino, acceso, alcance y datos; aprovisionamiento, revisión humana y decisiones externas pueden dominar el calendario.

## 7. Correspondencia con el inventario anterior P01–P21

| Pendiente anterior | Estado al corte / tratamiento | Nuevo trabajo |
|---|---|---|
| P01 · Paridad Spark | Documentada previamente; falta expediente consolidado | A02, E04 |
| P02 · Spark SQL | Estado contradictorio entre documentos; no cerrado aquí | A01, E04 |
| P03 · T-SQL | Sin ejecución en SQL Server confirmada | E02 |
| P04 · DDL | Falta validación y carga del modelo, no solo crear tablas | A06, E01 |
| P05 · DAX | Sin ejecución en motor DAX confirmada | E03 |
| P06 · Fabric | Notebook no validado allí | E04 si es el destino elegido |
| P07 · Databricks | Notebook no validado allí | E04 si se decide validar esa alternativa |
| P08 · Optimización | SQLite documentado; SQL Server pendiente | E06 |
| P09 · Proveedor IA | Política/condiciones no verificadas en esta revisión | U09 |
| P10 · 34 etiquetas | Revisión humana pendiente | A13, U05 |
| P11 · Tickets nuevos | No existen textos nuevos suficientes en el caso | U06, A13 |
| P12 · Definición y dueños | Contrato del caso implementado; aceptación organizacional pendiente | U03, A05 |
| P13 · Fecha | Diferencia 21/31 octubre sin resolver | U01, A01 |
| P14 · Licencias y costos | Sin cotización; no reutilizar afirmaciones comerciales como vigentes | U09 |
| P15 · QA visual | Avanzado: dos presentaciones probadas en escritorio/móvil | A01 para actualizar estado; revisión impresa integral opcional |
| P16 · Reporte real | Código probado localmente, ODBC pendiente | E02, A14 |
| P17 · Credenciales | Exposición declarada; confirmar aplicabilidad y revocación | U10, A03 |
| P18 · Umbrales | Sin calibración con historial operativo | U08, A16 |
| P19 · Evidencias | Hay nuevas evidencias parciales, falta paquete completo | A02 |
| P20 · APP | Cálculo y CSV disponibles: +19,22 % junio–septiembre 2026 | A01 para cerrar documentalmente con enlace |
| P21 · TIENDA 2025 | Contraste disponible; no permite resolver causalidad/estacionalidad | A01 para actualizar la conclusión y el criterio de cierre |

Las doce brechas D01–D12 de la presentación ejecutiva se distribuyen aquí: modelo destino → A06; borrados/ventana → A10; maestro/incidencias → A09; esquema/escala → A07 y E06; recuperación/concurrencia → A17/E04; CI/observabilidad → A15–A17; seguridad/respaldos → U09/E05; meses vacíos → A04/A05; soporte/reporte → A11/A14; cliente LLM → A12; dinero/catálogos → A08; paquete reproducible → A01–A03.

## 8. Cómo cerrar cada tarea sin confundir avance con terminación

Usar una carpeta por tarea, por ejemplo `docs/evidencia/A04/`, con este registro:

```markdown
# A04 — Calendario mensual completo
- Estado: pendiente / en curso / preparado / validado local / validado destino / bloqueado / no aplica
- Fecha y responsable:
- Cambio realizado:
- Archivos afectados:
- Entorno y versiones:
- Comando o procedimiento:
- Resultado esperado:
- Resultado observado:
- Pruebas omitidas y motivo:
- Evidencias adjuntas:
- Dependencia pendiente:
- Criterio de cierre cumplido:
```

**Reglas de cierre:**

1. “Preparado” significa que existe código o documentación; no significa que se ejecutó.
2. “Validado local” no se convierte en “validado en destino” por similitud de sintaxis.
3. Una decisión humana se cierra con la decisión registrada, no con un borrador generado.
4. Actualizar todos los documentos afectados cuando cambie un estado o cifra.
5. Si cambian reglas o datos, recalcular referencias; no forzar resultados para conservar los números históricos.
6. Conservar salidas agregadas y redactadas; no adjuntar claves ni datos personales innecesarios.

## 9. Qué no conviene hacer todavía

- Desplegar dos plataformas solo para afirmar que ambas están soportadas.
- Prometer ahorro o tiempos de SQL Server extrapolando el experimento SQLite.
- Cambiar definición de venta para adaptarla a producción sin mantener separada la resolución del caso.
- Usar el 100 % del conjunto sintético como prueba de calidad productiva del LLM.
- Reescribir todo el ETL antes de cerrar evidencia, contratos y puente al modelo destino.
- Añadir un orquestador complejo antes de definir frecuencia, volumen y necesidades de recuperación.
- Marcar como fallos reproducidos todas las observaciones de lectura: varias son riesgos de diseño o funcionalidades futuras.

## 10. Fuentes del diagnóstico

- [Enunciado](../enunciado/Prueba_Tecnica_Lider_Datos.md).
- [Mapa de entregables](../README.md) y [detalle del ETL](../README_ETL.md).
- [Inventario anterior de pendientes](PENDIENTES_EJECUCION.md).
- [Catálogo de calidad](02_catalogo_calidad.md), [SQL](01_sql_lectura.md), [DAX](03_dax.md), [optimización](05_optimizacion.md), [liderazgo](06_liderazgo.md) e [IA](07_clasificacion_ia.md).
- Código en `src/shared/andina_etl/`, `src/shared/spark/`, `src/shared/tickets_ia/`, `src/shared/reporte_ventas.py`, SQL, DDL y pruebas.
- [Presentación ejecutiva](presentacion_entrega.html) y [resolución por punto](presentacion_resolucion_prueba.html).

Este plan distingue hechos observados, ejecuciones previas documentadas y propuestas. No certifica producción ni afirma una revisión exhaustiva de todos los comportamientos posibles del sistema.
