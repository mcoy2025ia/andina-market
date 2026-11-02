# Roadmap de ejecución · guía detallada

> Versión ampliada de [12_roadmap_ejecucion.md](12_roadmap_ejecucion.md). Mismas
> cifras de referencia, mismos bloques (Databricks/Fabric/Power BI/SQL Server), mismas
> dependencias U01–U10 y E01–E05. Lo que añade: por qué el orden recomendado es ese y
> no otro, el razonamiento de costo detrás de cada palanca, una lectura más profunda de
> las dependencias entre tareas, y qué hacer si el tiempo disponible no encaja en
> ninguno de los tres escenarios de la versión corta.
>
> Los documentos detallados por herramienta están en
> [plataforma/databricks_detallada.md](plataforma/databricks_detallada.md),
> [plataforma/fabric_detallada.md](plataforma/fabric_detallada.md),
> [plataforma/powerbi_detallada.md](plataforma/powerbi_detallada.md) y
> [plataforma/sqlserver_detallada.md](plataforma/sqlserver_detallada.md).

**Corte:** 1 de noviembre de 2026.

---

## Por qué existe este documento y no solo los cuatro de herramienta

Los cuatro documentos por herramienta son correctos de forma aislada, pero ninguno
responde "¿y por dónde empiezo si solo tengo unas horas?" ni "¿qué pasa si hago Fabric
antes que Databricks?". Este documento es la capa de **secuenciación y prioridad**: la
misma información de las cuatro guías, vista desde la pregunta de en qué orden generan
más valor por hora invertida, y qué depende de qué.

## 1. Punto de partida, con el razonamiento detrás de cada cifra

(Mismas cifras de referencia que la versión corta: 6.040 clientes, 19.270/19.734
pedidos, 20.124/20.883 pagos, 7.925 filas Gold, 2.125 tickets, venta neta
COP 14.177.333.600.)

**Por qué estas cifras —y no otras— son la vara de medir en las cuatro plataformas:**
son las mismas que produce el pipeline local (`scripts/cargar_datos.py`) sobre los CSV
de `data/original/` sin modificarlos. Como el ETL local y las versiones Spark/SQL del
proyecto están diseñadas para implementar **la misma regla de negocio** (venta neta =
`valor_bruto − descuento` de pedidos `ENTREGADO`, atribuida a `fecha_pedido`, rango
2025-01-01 a 2026-09-30 — ver
[CLAUDE.md](../CLAUDE.md#arquitectura)), cualquier plataforma que ejecute el mismo CSV
de entrada con el mismo código debería llegar exactamente a las mismas cifras. Una
diferencia no es "normal variación entre motores": es evidencia de que algo en esa
plataforma concreta interpretó una regla distinto, y por diseño del roadmap **eso se
reporta, no se ajusta** para que coincida.

**Por qué 19.270 de 19.734 y no "19.734 pedidos válidos":** la diferencia (464 pedidos)
son los que caen en cuarentena por violar alguna regla de calidad (fechas fuera de
rango, valores no positivos, duplicados, etc. — ver
[docs/02_catalogo_calidad.md](02_catalogo_calidad.md)). Esa diferencia es intencional y
debe reproducirse igual en cada plataforma: si una plataforma da 19.734 pedidos
"válidos" en Gold, significa que sus reglas de calidad no están corriendo, no que tuvo
mejor suerte con los datos.

### El perfil de Databricks roto: por qué se menciona aquí y no solo en databricks.md

Se repite en este documento porque es, literalmente, el primer obstáculo de toda la
secuencia si decides empezar por Databricks o Fabric con un token de Azure AD compartido
entre ambos: un perfil de CLI inválido bloquea **todo** lo que dependa de la línea de
comandos (DBX-02 a DBX-05, DBX-09), aunque la UI web funcione bien. Resolverlo primero
(10 minutos) evita descubrir el bloqueo a mitad de una tarea más larga.

### La decisión del motor T-SQL, explicada

La tabla de la versión corta (Docker / Azure SQL / Fabric Warehouse) resume **qué se
pierde** con cada opción. La razón de fondo de por qué Fabric Warehouse "no sirve para
E02" específicamente —y sí para FAB-08— es que E02 mide **planes de ejecución y
operadores físicos** (Index Seek vs. Scan, lecturas lógicas), que son artefactos del
optimizador de **SQL Server** concretamente; el optimizador de Fabric Warehouse es
compatible en sintaxis T-SQL pero es un motor distinto, columnar y distribuido sobre
OneLake, con su propio modelo de costos. Ver el desarrollo completo en
[plataforma/sqlserver_detallada.md](plataforma/sqlserver_detallada.md#conceptos-antes-de-empezar).

---

## 2. El orden importa más que la lista — con el razonamiento completo

### Por qué Power BI es "la tarea de mayor retorno" y no, por ejemplo, Databricks

Dos factores se multiplican, no se suman: **cuánto cuesta cerrarla** (3 h, la más barata
de las cuatro) y **cuánto pesa la afirmación que cierra** (si las medidas DAX nunca se
probaron en un motor real, es la primera pregunta que hace cualquier evaluador de BI, y
hoy la respuesta honesta es "no"). Databricks completo (8 h) cierra una afirmación
igualmente importante (E04), pero a más del doble del costo — por eso, con tiempo
limitado, Power BI gana en la relación valor/hora, no en importancia absoluta.

### Por qué Fabric **antes** de Power BI en el escenario de la semana completa

La dependencia es puramente mecánica: [FAB-09](plataforma/fabric_detallada.md#fab-09--modelo-semántico-direct-lake)
crea el modelo semántico Direct Lake con las relaciones ya hechas, y
[PBI-01 Ruta A](plataforma/powerbi_detallada.md#pbi-01--conectar-el-modelo-️-30-min) lo
reutiliza directamente. Si en cambio haces Power BI **antes** de Fabric, tienes que usar
la Ruta B (Power BI Desktop contra Databricks o contra los datos locales) y rehacer las
relaciones desde cero en PBI-02 — el mismo trabajo, pero sin aprovechar lo que FAB-09 ya
deja hecho. No es que Power BI "necesite" Fabric: es que hacerlo en ese orden ahorra una
hora real.

### Por qué Databricks y Fabric no se subordinan entre sí en las dependencias

A diferencia de Fabric→Power BI, Databricks y Fabric son **independientes** entre sí:
ambos ejecutan el mismo notebook generado por `build_notebook.py` sobre el mismo CSV,
sin que el resultado de uno alimente al otro. El escenario de la semana completa los
pone en días consecutivos (2 y 3) por conveniencia de planificación, no por una
dependencia real — podrías invertir el orden, o hacer solo uno de los dos, sin que eso
rompa nada del otro.

### Un cuarto escenario: si el tiempo disponible no encaja en ninguno de los tres de la versión corta

La versión corta cubre "3 horas", "2 días" y "la semana completa". Si tienes, por
ejemplo, **un solo día completo (6-8 h)**:

| Opción | Qué hacer | Por qué |
|---|---|---|
| **A · Máximo cierre de afirmaciones débiles** | Power BI completo (3 h) + SQL Server SQL-01 a SQL-04 (DDL y carga, sin la parte de optimización, ~1,5 h) | Cierra E03 completo y la mitad de E01/E02 con DDL y carga reales, dejando la medición de planes para otro día |
| **B · Un solo bloque Delta completo** | Databricks DBX-01 a DBX-08 (E04 completo) | Si lo que más te interesa demostrar es que el notebook corre de verdad en la nube con los doce escenarios, en vez de repartir el día entre varias afirmaciones parciales |
| **C · La pregunta de arquitectura más interesante** | Fabric FAB-01 a FAB-08 (E04 en Fabric + la prueba de transacción) | Si la pregunta "¿por qué Delta y no una transacción real?" es la que más te preocupa defender en la sustentación |

La guía para decidir entre A/B/C: A maximiza **cuántas afirmaciones distintas** dejan de
ser "escrito, no ejecutado"; B y C profundizan **una sola** afirmación hasta el fondo.
Si no sabes cuál prefiere el evaluador, A es la apuesta más segura.

---

## 3. Dependencias, con el razonamiento de cada flecha

(Mismo diagrama de dependencias que la versión corta.)

```
DBX-01 perfil ──► DBX-02..DBX-06 ──► DBX-07 (serverless) ──► DBX-08 (escenarios)
                                                     └──► DBX-09 (bundle) ──► E05

FAB-01 capacidad ──► FAB-02..FAB-05 ──► FAB-07 (escenarios)
                                   ├──► FAB-08 (transacción) ──► lámina 18 del deck
                                   └──► FAB-09 (modelo) ──► PBI-01 (ruta A)

SQL-01 docker ──► SQL-02 DDL ──► SQL-03 carga ──► SQL-04 consultas
                                            └──► SQL-05 volumen ──► SQL-06/07 planes

U05 (34 etiquetas) ──► E06  [bloqueante: sin esto no hay IA validada]
```

**Por qué DBX-07 (serverless) está "entre" DBX-06 y DBX-08 y no es paralelo:** DBX-08
corre los doce escenarios, incluyendo E04-08 (el fallo entre tablas), y conviene
ejecutarlos en el cómputo final que vas a usar en producción (idealmente serverless, por
costo). Si corres los doce escenarios en clásico y luego migras a serverless, tendrías
que repetir al menos el escenario más sensible para confirmar que el comportamiento no
cambia con `.cache()` resuelto de otra forma.

**Por qué DBX-09 (bundle) depende de DBX-08 y no solo de DBX-06:** desplegar el
notebook como job programado sin haber corrido los doce escenarios significaría
desplegar a producción un pipeline cuyo comportamiento ante fallos (E04-06 a E04-10) no
se verificó — el orden refleja que **desplegar** y **validar comportamiento ante
fallos** son cosas distintas, y la segunda debería preceder a la primera.

**Por qué FAB-08 no depende de FAB-07:** es la única rama del diagrama de Fabric que no
necesita los doce escenarios completos — solo necesita FAB-01 a FAB-05 (capacidad,
Lakehouse, notebook corriendo) porque la prueba de transacción multi-tabla ocurre en un
**Warehouse separado**, no en el Lakehouse. Puedes hacer FAB-08 inmediatamente después
de FAB-05 si la pregunta de arquitectura es tu prioridad, sin esperar a FAB-07.

**Por qué SQL-05/06/07 dependen de SQL-02/03/04 y no pueden adelantarse:** necesitas que
el esquema (`SQL-02`) y los datos reales (`SQL-03`) existan antes de poder generar
volumen sintético sobre ellos (`SQL-05`) — no tendría sentido medir un plan de ejecución
sobre una tabla que replica una estructura que ni siquiera se confirmó que es correcta.

**Por qué U05 (34 etiquetas) es la única dependencia marcada "bloqueante" fuera del
mundo de plataformas:** a diferencia de U01-U04 y U06-U10, que bloquean partes
específicas, U05 bloquea **todo E06** sin excepción: sin etiquetas revisadas por
humanos, no existe ninguna etiqueta que `fact_ticket.tipo_caso` pueda admitir (ver
[CLAUDE.md](../CLAUDE.md#arquitectura): *"solo admite etiquetas en estado `REVISADA`"*),
así que no hay ningún subconjunto de E06 que se pueda avanzar sin esa decisión tuya.

---

## 4. Las tres tareas que más valen, con el argumento completo de por qué

### 1. PBI-06 · Verificar las medidas DAX — 3 h

Ya razonado arriba (sección 2) y en detalle en
[plataforma/powerbi_detallada.md](plataforma/powerbi_detallada.md#preguntas-frecuentes-de-este-bloque).
El argumento resumido: menor costo de las tres, afirmación más repetida en preguntas de
sustentación.

### 2. FAB-08 · ¿Warehouse soporta transacción multi-tabla? — 45 min

El argumento no es solo "es barato" (lo es): es que convierte la pieza **más citada**
del diseño de arquitectura del proyecto —por qué Delta usa un puntero de publicación en
vez de una transacción— de una explicación teórica a un hecho verificado con una prueba
de `ROLLBACK`/`COMMIT` de dos líneas. Ver el desarrollo completo en
[plataforma/fabric_detallada.md](plataforma/fabric_detallada.md#fab-08--la-prueba-que-solo-fabric-permite-️-45-min-).

### 3. SQL-07 · Medir la optimización con planes reales — 30 min

El argumento: el experimento existente (SQLite) ya identificó **la causa correcta**
(un `CAST` que rompe la capacidad de usar el índice — ver
[plataforma/sqlserver_detallada.md](plataforma/sqlserver_detallada.md#por-qué-el-cast-del-enunciado-original-fuerza-un-scan-el-corazón-de-sql-0607)),
pero en un motor que el enunciado no pide. SQL-07 no repite el experimento: lo traslada
al motor correcto con la menor inversión de tiempo de las tres tareas.

### La cuarta, no técnica: las 34 etiquetas (U05)

Se mantiene aparte de las tres anteriores porque no es una tarea de plataforma ni de
ejecución de código — es una decisión humana de calidad de dato que ningún script puede
sustituir por diseño (ver
[docs/REVISION_HUMANA_IA.md](REVISION_HUMANA_IA.md)). Se incluye en esta lista porque,
en términos de "qué desbloquea más con menos esfuerzo humano", dos horas de revisión
abren un bloque completo (E06) que de otra forma queda permanentemente cerrado, sin
importar cuánto tiempo de plataforma se invierta en lo demás.

---

## 5. Decisiones todavía tuyas — con el porqué de cada una

(Misma tabla U01-U10 de la versión corta. El porqué de las dos marcadas "las caras":)

**Por qué U03 (pesos enteros o centavos; devoluciones; categorías) es cara de cambiar
después de empezar:** la regla "pesos enteros exactos" no vive en un solo archivo —
atraviesa `config.py`/`rules.py` (validación), `store.py` (tipos DuckDB), las cuatro
variantes de SQL (tipos de columna) y `fabric/semantic_model/medidas.dax` (si las
medidas asumen enteros en algún punto de formato o redondeo). Cambiarla implica una
pasada coordinada por los cinco lugares a la vez, no un cambio aislado — exactamente lo
que [CLAUDE.md](../CLAUDE.md#arquitectura) describe como "decisiones de negocio que
atraviesan varios archivos".

**Por qué U04 (contrato de fuente: snapshot o incremento) es cara de resolver tarde:**
sin ese contrato, el pipeline no puede distinguir honestamente entre "esta fila ya no
está en el CSV porque se dio de baja" y "esta fila no está porque la extracción falló
parcialmente" — y una vez que el sistema empieza a tratar ausencias de una forma u otra,
cambiar de interpretación después implica reconstruir el historial de qué se consideró
baja válida y qué no, con el riesgo de borrar datos que en realidad nunca debieron
considerarse ausentes.

### Cómo cerrar U05, con el razonamiento de cada paso del proceso

(Mismos comandos de la versión corta: plantilla ya existe → completar cuatro columnas →
`revision_etiquetas.py auditar` → `importar_etiquetas.py revision` → `cargar_datos.py`.)

**🧠 Por qué el script de auditoría corre *antes* de importar, no después:**
`revision_etiquetas.py auditar` comprueba formato, acuerdo entre anotadores y fugas de
información **sobre el CSV que tú llenaste**, sin tocar la base de datos — es la
oportunidad de corregir un problema (una fila sin motivo, un desacuerdo no resuelto)
antes de que `importar_etiquetas.py` intente aplicarlo, y ese script está diseñado para
negarse si algo falta en vez de importar parcialmente.

**🧠 Por qué "no uses otra IA" para la revisión, incluso una IA distinta de la que
propuso la etiqueta original:** el propósito de la revisión humana no es "tener una
segunda opinión cualquiera" — es tener una fuente de verdad que **no comparte los
sesgos ni errores sistemáticos** de ningún clasificador automático. Si el segundo
anotador fuera también una IA (aunque fuera un modelo distinto), la "validación humana"
dejaría de ser lo que `gold.fact_ticket.tipo_caso` exige por diseño
(ver [CLAUDE.md](../CLAUDE.md#arquitectura): *"es la garantía de que una propuesta no se
publique como validada"*), y toda la cadena de evaluación posterior (E06) perdería su
punto de apoyo.

---

## 6. Qué me devuelves — con el porqué de cada exigencia

(Mismos cuatro puntos de la versión corta: qué ejecutaste, qué salió, si coincidió, y
contexto.)

**Por qué "el error exacto, sin resumir" y no un resumen del problema:** un resumen
("falló la carga de pedidos") pierde precisamente la información que permite distinguir
entre las cuatro o cinco causas más probables de cada error (ver los catálogos
extendidos de error en cada documento de herramienta) — el mensaje textual completo, el
código de error y la línea exacta son lo que convierte "algo falló" en un diagnóstico
reproducible.

**Por qué se pide "contexto" (fecha, workspace, región, tipo de cómputo) y no solo el
resultado numérico:** porque el mismo hallazgo puede depender de la versión del runtime,
la región (latencia, disponibilidad de SKU) o el tipo de cómputo (clásico vs.
serverless) — sin ese contexto, un hallazgo de hoy podría no reproducirse en una sesión
distinta sin que quede claro por qué, confundiendo "se corrigió" con "cambió el entorno".

---

## 7. Control de costo — con el razonamiento económico detrás de cada palanca

(Misma tabla de riesgos/palancas de la versión corta.)

**El principio común a las cuatro plataformas:** en todas, el cómputo se factura por
estar **activo**, no por estar **en uso** — la diferencia entre "encendido" y
"trabajando" es, con pequeñas variaciones de implementación, donde vive la mayoría del
desperdicio de costo en experimentos cortos como este roadmap:

- Databricks: un clúster clásico cobra desde `RUNNING` hasta su apagado (auto-termination
  o manual); serverless factura por cómputo real consumido —ver
  [databricks_detallada.md](plataforma/databricks_detallada.md#por-qué-serverless-cambia-el-comportamiento-y-por-qué-cache-falla-ahí).
- Fabric: la capacidad entera cobra por estar activa, uses o no CU en un momento dado
  —ver [fabric_detallada.md](plataforma/fabric_detallada.md#por-qué-todo-cuelga-de-una-capacidad).
- SQL Server en Docker: el contenedor corriendo consume recursos de tu máquina local
  (no de un proveedor cloud), pero sigue valiendo la pena `docker stop` por higiene y
  para liberar el puerto 1433 para otro uso.
- Jobs programados: dejarlos en `PAUSED` hasta decidir operarlos de verdad evita que un
  experimento de validación se convierta, sin que nadie lo decidiera, en un proceso de
  producción real cobrando cada noche.

**Por qué `performance_target: STANDARD` y no `PERFORMANCE_OPTIMIZED` en el job de
Databricks:** un ETL de lote nocturno sin nadie esperando el resultado no tiene ningún
requisito de latencia que justifique pagar la tarifa de cómputo optimizado para
velocidad; `STANDARD` arranca en minutos (suficiente para un proceso que corre una vez
al día) a un costo por DBU menor.

---

## 8. Estado: antes y después

(Misma tabla de la versión corta: 8 afirmaciones en "escrito, no ejecutado" hoy, bajan a
2 tras los días 1-5 del plan semanal — el transporte SMTP y la validación de IA, que
dependen de decisiones U07/U05-U06, no de ejecución de plataforma.)

**Por qué quedan exactamente 2 y no 0 aunque se complete todo el plan de plataformas:**
porque esas dos afirmaciones no son de ejecución técnica sino de **autorización y
decisión humana** — enviar un correo real (U07) y validar un clasificador contra una
muestra real de tickets etiquetados por personas (U05/U06) no son algo que una sesión de
plataforma pueda cerrar por sí misma, por diseño: el proyecto se niega deliberadamente a
simular esas dos decisiones en lugar de esperar a que se tomen.

## Glosario transversal

| Término | Qué significa aquí |
|---|---|
| **E01–E05** | Los cinco bloques de validación en entorno real que dependen de credenciales/plataforma (SQL Server, T-SQL/optimización, DAX, Delta cloud, despliegue) |
| **E06** | Validación de la clasificación de tickets con muestra real, bloqueada por U05/U06 |
| **U01–U10** | Las diez decisiones que solo el autor del proyecto puede tomar; ninguna IA puede sustituirlas |
| **"Escrito, no ejecutado"** | Código o SQL que existe y pasó pruebas locales/sintéticas, pero nunca corrió contra la plataforma real que el enunciado pide |
| **Write-audit-publish** | El patrón de `run_id` + puntero de publicación que sustituye a una transacción multi-tabla en Delta (ver databricks_detallada.md) |

## Para profundizar

- El detalle paso a paso de cada bloque está en los cuatro documentos `_detallada.md`
  de `docs/plataforma/`.
- El estado y las cifras de referencia completas están en
  [ESTADO_IMPLEMENTACION.md](ESTADO_IMPLEMENTACION.md) y
  [PENDIENTES_ACTUALES.md](PENDIENTES_ACTUALES.md).
- El diseño de publicación por puntero está desarrollado en
  [08_traslado_delta.md](08_traslado_delta.md).
