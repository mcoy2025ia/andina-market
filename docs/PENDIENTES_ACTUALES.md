# Pendientes actuales de Andina Market

Actualizado: 1 de noviembre de 2026. Este archivo recoge lo que falta después del bloque A01–A18; sustituye al diagnóstico inicial para planificar el trabajo restante.

- **Repositorio privado:** https://github.com/mcoy2025ia/andina-market
- **Estado de las 18 tareas y evidencias:** [ESTADO_IMPLEMENTACION.md](ESTADO_IMPLEMENTACION.md).
- **CI aprobada del código:** https://github.com/mcoy2025ia/andina-market/actions/runs/41323664358

## 1. Base ya completada: no repetir como pendiente

Repositorio creado y cargado; ETL local con soporte y modelo estrella; contratos CSV; precisión de pesos enteros; calendario SQL completo; revalidación de relaciones; diagnóstico de ausencias; cliente LLM reforzado; reporte HTML local; compuertas de publicación; respaldo/restauración local; CI remoto y documentación de sustentación.

Evidencia: 116 pruebas locales aprobadas, dos módulos Spark omitidos localmente y 6 pruebas Spark aprobadas por separado en CI. Venta neta conciliada con recálculo independiente: COP 14.177.333.600. Segunda carga sin cambios en hechos. Presentaciones revisadas en escritorio y móvil; PDF de arquitectura revisado en sus dos páginas.

Esto acredita la implementación local y las pruebas indicadas. No acredita despliegue productivo ni ejecución en SQL Server, Power BI, Fabric o Databricks.

## 2. Lo que podemos avanzar ya con IA

Estas tareas no requieren credenciales de producción. Son trabajo restante o ampliaciones de preparación, no fallos de la CI existente.

| ID | Pendiente | Entregable / criterio de cierre | Prioridad |
|---|---|---|---|
| IA-R01 | Completar la revisión de impresión de las presentaciones HTML | Exportar y revisar todas las páginas; corregir cortes, tablas y bloques largos. El PDF de arquitectura ya fue revisado; las presentaciones completas aún no tienen certificación página a página. | P1 si se entrega PDF |
| IA-R02 | Preparar el traslado de las extensiones locales al flujo Delta | Diseñar y adaptar soporte, estrella, contratos, incidencias y publicación consistente; pruebas de código y lista de escenarios cloud. La ejecución real se cierra en E04. | P1 si se elige cloud |
| IA-R03 | Preparar el flujo de incorporación de etiquetas revisadas | Importación versionada, validación de taxonomía/procedencia y asociación a tickets; conservar estados propuesta/revisada. `fact_ticket.tipo_caso` no debe poblarse como validado usando etiquetas no revisadas. | P2 |
| IA-R04 | Completar el arnés para evaluar una muestra reservada | Métricas por clase, matriz de confusión, intervalos, errores críticos y registro de costo/latencia. Probar con datos sintéticos; el resultado real depende de una muestra nueva y anotación humana. | P2 |
| IA-R05 | Preparar pruebas de integración del transporte del reporte | Simular éxito, fallo, reintento y duplicado; documentar configuración sin secretos. No realizar envíos reales sin destinatarios y autorización explícita. | P2 |
| IA-R06 | Ensayar la sustentación contigo | Simulacro de diez minutos, preguntas sobre decisiones y cambio controlado. El guion y el ensayo técnico ya existen; falta practicar contigo y corregir vacíos de comprensión. | P0 entrega |

P0: necesario para cerrar la entrega o una afirmación que se haga en ella. P1: integración prioritaria. P2: ampliación operativa/productiva. No es necesario convertir toda la propuesta cloud en producción para presentar honestamente la prueba técnica.

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

### E04 · Delta en Fabric o Databricks — P1/P2

- Spark de reglas y SQL ya está aprobado en CI; esa parte deja de ser pendiente.
- Falta adaptar/verificar las extensiones de orquestación y ejecutar primera/segunda carga, modificaciones, pagos tardíos, retiradas, MERGE/DELETE, fallos entre tablas y recuperación.
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

1. **Cerrar entrega:** U01/U02, revisar las 34 etiquetas y practicar sustentación. IA-R01 solo si se exige entregar las presentaciones en PDF.
2. **Validar extremo a extremo:** habilitar SQL Server/Power BI de prueba; ejecutar E01, E02 y E03.
3. **Acordar operación:** cerrar contratos U03/U04 y objetivos U07/U08.
4. **Elegir piloto cloud:** preparar IA-R02 y ejecutar E04 en un solo destino inicialmente.
5. **Ampliar IA y producción:** muestra independiente, E06 y E05 según prioridad y presupuesto.

## 6. Cuándo podemos declarar cerrado el proyecto

**Como entrega de prueba técnica:** documentación coherente, artefactos accesibles, evidencia reproducible, limitaciones explícitas y sustentación practicada. Las partes propuestas deben seguir identificadas como propuestas.

**Como solución productiva:** además, integración real del destino, contratos acordados, operación y recuperación verificadas, permisos/monitoreo y validación humana de IA. Este segundo nivel todavía no está cerrado.
