# Pendientes actuales de Andina Market

Actualizado: 1 de noviembre de 2026 (segunda revisión del día, tras cerrar IA-R01 a IA-R05). Este archivo recoge lo que falta después del bloque A01–A18; sustituye al diagnóstico inicial para planificar el trabajo restante.

- **Repositorio privado:** https://github.com/mcoy2025ia/andina-market
- **Estado de las 18 tareas y evidencias:** [ESTADO_IMPLEMENTACION.md](ESTADO_IMPLEMENTACION.md).
- **CI aprobada del código:** https://github.com/mcoy2025ia/andina-market/actions/runs/41323664358

## 1. Base ya completada: no repetir como pendiente

Repositorio creado y cargado; ETL local con soporte y modelo estrella; contratos CSV; precisión de pesos enteros; calendario SQL completo; revalidación de relaciones; diagnóstico de ausencias; cliente LLM reforzado; reporte HTML local; compuertas de publicación; respaldo/restauración local; CI remoto y documentación de sustentación.

Evidencia: 116 pruebas locales aprobadas, dos módulos Spark omitidos localmente y 6 pruebas Spark aprobadas por separado en CI. Venta neta conciliada con recálculo independiente: COP 14.177.333.600. Segunda carga sin cambios en hechos. Presentaciones revisadas en escritorio y móvil; PDF de arquitectura revisado en sus dos páginas.

Esto acredita la implementación local y las pruebas indicadas. No acredita despliegue productivo ni ejecución en SQL Server, Power BI, Fabric o Databricks.

## 2. Lo que podemos avanzar ya con IA

Estas tareas no requieren credenciales de producción. **IA-R01 a IA-R05 están cerradas**; queda IA-R06, que necesita tu participación.

| ID | Pendiente | Estado | Evidencia / qué queda |
|---|---|---|---|
| IA-R01 | Revisión de impresión de las presentaciones HTML | **Cerrado** | `scripts/qa_impresion.py` audita las tres páginas y da 0 hallazgos; se corrigieron los cortes de bloque, el encabezado repetido de tablas y una página que quedaba con una sola línea. PDF exportados en `docs/evidencia/impresion/`; inventario de las 102 páginas en `qa_impresion.json`. Pruebas: `tests/test_impresion.py`. |
| IA-R02 | Traslado de las extensiones locales al flujo Delta | **Cerrado como diseño y código** | `src/shared/spark/extensiones_spark.py` + notebook regenerado (13 celdas). 19 pruebas comparan la estrella completa contra DuckDB fila a fila. Diseño y escenarios en [08_traslado_delta.md](08_traslado_delta.md). **La ejecución real sigue siendo E04.** |
| IA-R03 | Incorporación de etiquetas revisadas | **Cerrado** | `src/shared/andina_etl/etiquetas.py` y `scripts/importar_etiquetas.py`: importación versionada, validación de taxonomía y procedencia, asociación por hash de texto. `fact_ticket.tipo_caso` solo admite decisiones humanas; la propuesta vive en `tipo_caso_propuesto`. Pruebas: `tests/test_etiquetas.py`. Falta **U05** para que haya algo que importar. |
| IA-R04 | Arnés para evaluar una muestra reservada | **Cerrado** | `src/shared/tickets_ia/evaluacion.py` y `clasificar_tickets.py reservada`: intervalos de Wilson, matriz de confusión, errores críticos, detección de fugas y telemetría de costo/latencia. Probado con la partición sintética. Falta **U06** para que el resultado signifique algo. |
| IA-R05 | Transporte del reporte | **Cerrado** | `src/shared/reporte_envio.py` y `scripts/despachar_reporte.py`: éxito, fallo permanente, reintento con espera creciente y omisión de duplicados por hash de contenido. Configuración sin secretos en [09_reporte_envio.md](09_reporte_envio.md). Pruebas: `tests/test_reporte_envio.py`. No envía nada sin **U07**. |
| IA-R06 | Ensayar la sustentación contigo | **Abierto · P0** | El guion y el ensayo técnico existen. Falta practicarlo contigo y corregir vacíos de comprensión; no puede hacerse sin ti. |

P0: necesario para cerrar la entrega o una afirmación que se haga en ella. No es necesario convertir toda la propuesta cloud en producción para presentar honestamente la prueba técnica.

Lo que estas cinco tareas **no** cambian: ninguna ejecuta SQL Server, Power BI, Fabric ni Databricks, y ninguna sustituye una decisión tuya. IA-R03, IA-R04 y IA-R05 dejan el mecanismo listo y bloqueado a la espera de U05, U06 y U07 respectivamente: por diseño, se niegan a funcionar sin esas decisiones en lugar de inventarlas.

## 3. Lo que debes decidir o aportar tú

| ID | Acción tuya | Detalle y criterio de cierre | Qué hará después la IA |
|---|---|---|---|
| U01 | Confirmar fecha y forma efectiva de entrega | Resolver discrepancia histórica 21/31 de octubre con tu citación; confirmar formato y destinatario. No inventar prórroga. | Actualizar fecha y portada definitivas. |
| U02 | Confirmar acceso del evaluador | El repositorio privado y el ZIP ya existen. Falta definir si compartes ZIP o das acceso al evaluador; la elección de GitHub ya está resuelta. | Preparar instrucciones de revisión y entrega. |
| U03 | Ratificar reglas de negocio | Pesos enteros o centavos/redondeo; devoluciones; canales/categorías; fecha y zona horaria; denominador y madurez de recompra; SLA de tickets. Mantener los supuestos del caso hasta una decisión explícita. | Ajustar código, contratos y pruebas de impacto. |
| U04 | Confirmar contrato de fuentes | Snapshot completo o incremento, campo de actualización, bajas, retrasos y correcciones. Sin ese contrato, ausencia de una fila no autoriza borrarla. | Implementar adaptador/bajas y reconciliación acordados. |
| U05 | Revisar las 34 etiquetas | Completar anotadores, decisión final y motivo en [revision_etiquetas_34.csv](revision_etiquetas_34.csv), según [guía](REVISION_HUMANA_IA.md). No sustituir revisión humana por otra IA. | Auditar campos, acuerdo, discrepancias y cargar las decisiones. |
| U06 | Aportar muestra real independiente | Tickets nuevos autorizados, representativos y etiquetados por personas; no reutilizar los 34 textos conocidos ni declarar sintéticos como reales. | Ejecutar evaluación reservada y analizar errores. |
| U07 | Definir reporte y autorizar envío | Destinatarios, canal, horario, período y comportamiento ante datos no validados. La vista previa local no envía correo. | Integrar transporte y validar entrega controlada. |
| U08 | Acordar objetivos de operación | Frescura, volumen, cuarentena, tolerancia, responsables, escalamiento, RPO y RTO. Aportar historial para calibrar umbrales. | Configurar compuertas y ensayar incidentes/recuperación. |
| U09 | Habilitar un entorno de prueba y presupuesto | Elegir primero SQL Server/Power BI o un destino cloud; acceso seguro, permisos y límite de consumo. No hace falta habilitar ambas nubes. | Ejecutar las validaciones E01–E05. |
| U10 | Resolver credenciales señaladas, si aplica | Confirmar revocación de cualquier clave real previamente expuesta. La contraseña del enunciado fue redactada; no se presume operativa. No compartir secretos en el chat. | Mantener configuración y evidencias sin secretos. |

## 4. Trabajo conjunto que depende de un entorno o de tus decisiones

### E01 · Modelo estrella en SQL Server — P1

- Ya existe el modelo local y el cargador con modo de planificación.
- Falta ejecutar DDL y carga en una base de prueba autorizada, revisar tipos, restricciones e índices y conciliar al mismo grano.
- Cierre: conteos y venta neta coinciden con la referencia; registrar motor y resultados. La compatibilidad monetaria debe verificarse en los tipos del destino.

### E02 · T-SQL, optimización y ODBC — P1

- Ejecutar ventas/cohortes y reporte contra SQL Server, incluidos meses sin ventas y períodos comparables.
- Medir la optimización en el motor real con planes, lecturas y tiempos. Las pruebas SQLite no sustituyen esa evidencia.
- Cierre: comparación por fila con resultados locales, consulta parametrizada y conexión ODBC de lectura comprobada, sin publicar cadenas de conexión.

### E03 · Power BI y DAX — P1

- Construir o conectar el modelo, verificar calendario y relaciones; instalar y evaluar las medidas.
- Probar mes/año/canal, ausencia de pedidos y comparación de períodos equivalentes.
- Referencias del caso: enero 2026 COP 948.592.900; septiembre COP 795.114.800; enero–septiembre 2026 COP 7.739.061.400; base comparable 2025 COP 3.891.305.400.
- Cierre: resultados de motor con contexto de filtro registrado y artefacto del modelo. Tener DAX escrito no equivale a haberlo ejecutado.

### E04b · Compatibilidad del notebook con Databricks serverless — P1

Hallazgo de la revisión técnica del 1 de noviembre de 2026, **abierto y no corregido**.

- El notebook usa `.cache()` en cuatro puntos (celdas de pedidos y pagos). **Databricks
  serverless no admite `.cache()` ni `.persist()`**, así que hoy el notebook no corre en
  el modo de cómputo que es el predeterminado para trabajos y pipelines.
- El resto del código sí cumple: usa API de DataFrame y SQL, rutas `/Volumes/…` en vez
  de montajes DBFS, nombres de tres partes y ningún `sparkContext`, RDD ni
  `spark.conf.set` de memoria.
- Quitar el `.cache()` no basta: en la celda de pedidos sirve de hecho para materializar
  antes del `MERGE`, y el origen de ese `MERGE` lee la misma tabla que escribe
  (`silver_pedidos`, vía `hash_negocio`). La corrección correcta es **materializar en una
  tabla de staging** antes del `MERGE`, lo que además elimina esa autorreferencia.
- No se corrigió en esta revisión porque es código Delta que no se puede probar sin la
  plataforma; entra como parte de E04.
- Cierre: notebook ejecutado en serverless sin bloqueadores, y `performance_target`
  declarado (`STANDARD` para el lote nocturno).

### E04 · Delta en Fabric o Databricks — P1/P2

- Spark de reglas y SQL ya está aprobado en CI; esa parte deja de ser pendiente.
- **Las extensiones ya están adaptadas y probadas contra Spark real (IA-R02)**: soporte, estrella, contratos, incidencias y publicación consistente. Lo que queda es ejecutarlas en una plataforma.
- Falta ejecutar primera/segunda carga, modificaciones, pagos tardíos, retiradas, MERGE/DELETE, fallos entre tablas y recuperación. Los doce escenarios, con su resultado esperado y la evidencia a capturar, están en [08_traslado_delta.md](08_traslado_delta.md#4-escenarios-para-e04).
- Cierre: no duplicación, conciliación y ausencia de publicaciones parciales; evidencia del destino concreto. Validar Fabric no acredita Databricks ni viceversa.

### E05 · Operación productiva — P2

- CI remoto ya existe y pasó. Falta definir protecciones de rama/revisores y configurar las disponibles para el repositorio.
- Faltan promoción entre ambientes, programación, permisos, secretos gestionados, monitoreo y alertas al canal autorizado.
- Falta recuperación distribuida/Delta; el lock y respaldo actuales cubren la base local.
- Cierre: cambio defectuoso bloqueado, publicación incompleta retenida y restauración medida contra RPO/RTO acordados. El envío real de alertas requiere autorización explícita.

### E06 · IA y clasificación operativa — P2

- Requiere U05/U06 y política de privacidad, proveedor y presupuesto definidos.
- Ejecutar evaluación real independiente; determinar errores aceptables y tratamiento humano de ambiguos. La confianza del LLM no está calibrada.
- Incorporar etiquetas con trazabilidad y decidir si se permite enrutamiento automático. No está habilitado actualmente.
- Cierre: evaluación reproducible y aceptación humana del alcance; no presentar el 100 % sintético histórico como desempeño productivo.

## 5. Orden recomendado para continuar

1. **Cerrar entrega:** U01/U02, revisar las 34 etiquetas (U05) y practicar la sustentación (IA-R06). Los PDF de las presentaciones ya están exportados y revisados página a página.
2. **Validar extremo a extremo:** habilitar SQL Server/Power BI de prueba; ejecutar E01, E02 y E03.
3. **Acordar operación:** cerrar contratos U03/U04 y objetivos U07/U08.
4. **Elegir piloto cloud:** ejecutar E04 en un solo destino, siguiendo la tabla de escenarios de [08_traslado_delta.md](08_traslado_delta.md). El código ya está preparado (IA-R02).
5. **Ampliar IA y producción:** muestra independiente (U06), E06 y E05 según prioridad y presupuesto.

## 6. Cuándo podemos declarar cerrado el proyecto

**Como entrega de prueba técnica:** documentación coherente, artefactos accesibles, evidencia reproducible, limitaciones explícitas y sustentación practicada. Las partes propuestas deben seguir identificadas como propuestas.

**Como solución productiva:** además, integración real del destino, contratos acordados, operación y recuperación verificadas, permisos/monitoreo y validación humana de IA. Este segundo nivel todavía no está cerrado.
