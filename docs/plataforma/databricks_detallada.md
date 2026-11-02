# Databricks · guía detallada

> Esta es la versión ampliada de [databricks.md](databricks.md). Conserva los mismos
> identificadores de tarea (DBX-01…DBX-12), los mismos comandos y las mismas carpetas de
> evidencia, para que lo que ya hiciste con la versión corta siga valiendo. Lo que añade
> es: por qué cada mecanismo de la plataforma funciona así, más casos de error reales, un
> glosario y las preguntas que más se repiten en la sustentación sobre este bloque.
>
> Si vas con prisa, usa [databricks.md](databricks.md). Si quieres entender el
> mecanismo antes de ejecutar un paso —o te quedaste atascado y la tabla corta de
> errores no cubre lo que ves—, usa esta.

**Qué vas a lograr aquí:** lo mismo que en la versión corta: ejecutar el ETL completo en
Databricks con Delta, correr los doce escenarios de validación y dejarlo desplegado como
job. Cierra **E04**, el bloqueador **E04b** y parte de **E05**.

**Tiempo total:** 8 h repartibles, más el tiempo que tomes leyendo los recuadros de
concepto (opcional, no cuenta contra el presupuesto de la tarea).

---

## Conceptos antes de empezar

### Qué es Databricks realmente

Databricks no es "un Spark con interfaz". Es tres cosas separadas que conviene no
confundir, porque los errores de los primeros pasos casi siempre vienen de mezclarlas:

1. **El plano de control (control plane):** la UI web, el scheduler de jobs, el
   historial de notebooks. Vive en la nube de Databricks, no en tu cuenta de Azure/AWS/GCP.
2. **El plano de datos (data plane):** los clústeres de Spark que realmente ejecutan el
   código, y el almacenamiento (ADLS/S3/GCS) donde viven los archivos Parquet/Delta.
   Esto corre en **tu** cuenta de la nube.
3. **Unity Catalog:** la capa de gobierno que pone nombres de tres partes
   (`catalogo.esquema.tabla`) sobre archivos físicos, y que decide quién puede ver qué.
   Es compartido entre varios workspaces del mismo *metastore*.

Cuando el proyecto dice `andina.datos.silver_pedidos`, eso es
`catálogo.esquema.tabla` en Unity Catalog. No es una carpeta: es un nombre lógico que
Unity Catalog resuelve a una ubicación física (en un volumen `MANAGED`, la elige
Databricks; en uno `EXTERNAL`, la elige quien lo crea).

### Por qué un volumen y no `dbfs:/` a secas

Antes de Unity Catalog, Databricks solo tenía DBFS (Databricks File System), una capa
encima del almacenamiento de la cuenta, sin control de acceso fino. Un **volumen** es la
forma moderna de exponer archivos no tabulares (CSV, imágenes, modelos) con los mismos
permisos `GRANT`/`REVOKE` que las tablas. Por eso el notebook lee los CSV desde
`/Volumes/andina/datos/raw/...` y no desde una ruta DBFS suelta: así el mismo mecanismo
de gobierno (DBX-10) cubre tanto los datos crudos como las tablas Gold.

### Por qué serverless cambia el comportamiento (y por qué `.cache()` falla ahí)

Un clúster "clásico" es una máquina virtual que tú controlas: eliges el tamaño del
*driver* y los *workers*, y el estado (incluyendo lo que cachees en memoria) vive
mientras el clúster esté encendido. **Serverless** no te da una máquina: te da una
*sesión* efímera sobre un pool compartido que Databricks administra, y por diseño no
expone control fino sobre la memoria del clúster para evitar que una sesión afecte a
otra. Por eso ciertas operaciones de bajo nivel —entre ellas `.cache()`/`.persist()` en
algunas versiones del runtime serverless— no están disponibles o se comportan distinto.
Esto no es un bug del notebook: es la frontera deliberada entre "cómputo administrado
por ti" y "cómputo administrado por la plataforma". DBX-07 lo resuelve escribiendo el
resultado en una tabla *staging* en lugar de confiar en una caché en memoria —lo mismo
que tendrías que hacer en cualquier motor si quisieras que el resultado sobreviva al
proceso que lo generó.

### Por qué Delta no tiene transacción entre tablas (y qué hace el proyecto en su lugar)

Una tabla Delta es, por debajo, un directorio de archivos Parquet más un *log* de
transacciones (`_delta_log/`) que registra qué archivos son válidos en cada versión.
Cada tabla tiene **su propio log**. Una transacción ACID de Delta cubre una sola tabla:
no existe un mecanismo nativo para decir "escribe estas tres tablas o ninguna", como sí
puede hacer `BEGIN TRANSACTION ... COMMIT` en un motor relacional con un log de
transacciones compartido (ver [FAB-08 en fabric_detallada.md](fabric_detallada.md) para
el caso en que **sí** existe esa transacción).

La respuesta del proyecto —escribir los hechos marcados con `run_id` y mover un puntero
`publicacion_actual` solo si la conciliación pasa— es el patrón que en la literatura de
ingeniería de datos se llama a veces *write-audit-publish*: escribes en un lugar que
nadie lee todavía, auditas, y solo entonces "publicas" moviendo un puntero que sí leen
los consumidores (las vistas `v_fact_*`). El costo es que durante la ventana entre
"escribir" y "mover el puntero", las dos versiones (la publicada y la nueva) coexisten
en el storage: por eso el escenario **E04-08** es el más importante de todo el bloque,
porque es la única forma de *ver* ese diseño funcionando en vez de solo leerlo en el
código.

### DBU, no horas de máquina

Databricks no cobra por hora de máquina sino por **DBU** (Databricks Unit), una medida
de capacidad de cómputo normalizada que varía según el tipo de instancia y el producto
(Jobs, All-Purpose, SQL, Serverless tienen tarifas de DBU distintas). Por eso DBX-11 lee
`system.billing.usage`, que registra DBU consumidos, no horas: dos clústeres con el
mismo tiempo de pared pueden costar distinto si usan tipos de instancia distintos.

### OAuth U2M: qué pasa cuando corres `databricks auth login`

El comando abre el navegador porque usa el flujo OAuth "User-to-Machine": tu CLI no
conoce tu contraseña, y no debería. En su lugar, el servidor de autorización de
Databricks te muestra una pantalla de consentimiento, y si apruebas, le entrega al CLI un
*token* de acceso de corta duración más un *refresh token* para renovarlo sin que tengas
que volver a aprobar cada vez. Eso es lo que queda guardado (cifrado) bajo el perfil en
`~/.databrickscfg`. Por eso borrar la sección del perfil viejo no revoca nada en el
servidor: si quieres revocar acceso de verdad, hazlo desde la configuración de la cuenta
en la UI, no solo editando el archivo local.

---

## DBX-01 · Arreglar el perfil del CLI ⏱️ 10 min 🔴

(Mismos pasos que en la versión corta.)

**Pasos**

```bash
databricks auth profiles
databricks auth login --host https://dbc-ebd35512-279a.cloud.databricks.com --profile finanzauto
databricks auth profiles
databricks current-user me --profile finanzauto
```

**✅ Debe salir:** `finanzauto` con `Valid: YES`, y tu correo en `current-user me`.

**🧠 Qué pasa por debajo:** el login abre el navegador, negocia el token OAuth descrito
arriba y lo escribe en `~/.databrickscfg` bajo la sección `[finanzauto]`. El perfil
"viejo" con la URL pegada como nombre probablemente se creó pegando una URL completa de
notebook en el prompt interactivo de un login anterior en lugar del *hostname* del
workspace: el CLI tomó esa cadena literal como nombre de perfil.

**❌ Catálogo extendido de errores**

| Error | Causa | Qué hacer |
|---|---|---|
| *«cannot configure default credentials»* | Falta `--profile` en el comando | Añádelo a **todos** los comandos de esta guía |
| El perfil viejo con la URL larga sigue apareciendo | Quedó una sección `[https://dbc-...]` en `~/.databrickscfg` | Ábrelo en un editor y borra **solo** esa sección. No borres el archivo completo: otros perfiles podrían vivir ahí |
| `databricks current-user me` da `403` con el perfil nuevo | El usuario no tiene ninguna licencia/rol asignado en el workspace | Pide que un admin del workspace te agregue como usuario |
| El navegador no abre o el flujo se queda colgado | Política de red/proxy bloquea el *redirect* de OAuth | Prueba `databricks auth login --host ... --profile finanzauto` desde una red sin proxy corporativo, o pide un *personal access token* (PAT) como alternativa y usa `databricks configure --profile finanzauto` en su lugar |
| Dos perfiles válidos y el CLI usa el que no quieres | No pasaste `--profile` y existe un `DEFAULT` | Revisa `databricks auth profiles` y sé explícito siempre con `--profile finanzauto` |

**📎 Evidencia:** igual que la versión corta — `evidencia/databricks/01_perfil.txt`.

---

## DBX-02 · Crear catálogo, esquema y volumen ⏱️ 10 min

**Pasos** (idénticos a la versión corta)

```bash
databricks catalogs create --json '{"name": "andina"}' --profile finanzauto
databricks schemas create --json '{"name": "datos", "catalog_name": "andina"}' --profile finanzauto
databricks volumes create --json '{
  "catalog_name": "andina",
  "schema_name": "datos",
  "name": "raw",
  "volume_type": "MANAGED"
}' --profile finanzauto
```

**🧠 Qué pasa por debajo:** un catálogo y un esquema son solo metadatos en el
*metastore* de Unity Catalog — no ocupan espacio de almacenamiento por sí mismos. Un
volumen `MANAGED` sí reserva una ubicación física: Databricks elige dónde, dentro de la
ubicación de almacenamiento raíz asociada al metastore (o al catálogo, si tiene una
propia). Esa es la diferencia con un volumen `EXTERNAL`: ahí tú apuntas a una ubicación
de almacenamiento que ya existe y controlas (vía una *storage credential* y una
*external location*), típico cuando los datos ya viven en un *data lake* existente antes
de adoptar Databricks.

**❌ Catálogo extendido de errores**

| Error | Causa | Qué hacer |
|---|---|---|
| `PERMISSION_DENIED` creando el catálogo | No eres admin del metastore | Pide el permiso `CREATE CATALOG`, o usa un catálogo existente y ajusta `T()` en la celda 2 |
| `CATALOG_ALREADY_EXISTS` | Ya corriste DBX-02 antes (de una sesión previa) | No es un error real: verifica con `databricks catalogs list` y sigue a DBX-03 |
| El volumen se crea pero `databricks fs ls dbfs:/Volumes/...` falla | El volumen tarda unos segundos en estar listo tras crearse, o el nombre tiene un typo | Repite `databricks volumes list andina.datos --profile finanzauto` para confirmar el nombre exacto |
| `METASTORE_DOES_NOT_EXIST` o el comando pide un metastore | El workspace no tiene Unity Catalog habilitado | Esto es un bloqueador real de plataforma: sin UC no hay catálogos de tres partes; pide a un admin de cuenta que asigne un metastore al workspace |

**📎 Evidencia:** `evidencia/databricks/02_catalogo.txt`.

---

## DBX-03 · Comprobar si hay serverless ⏱️ 5 min

(Sin cambios respecto a la versión corta.)

**🧠 Por qué importa más de lo que parece:** serverless en Databricks no es solo "más
cómodo", cambia el modelo de costo de raíz. Un clúster clásico cobra desde que arranca
hasta que se apaga explícitamente (o hasta el *auto-termination*), incluyendo el tiempo
en que nadie lo está usando activamente pero sigue encendido entre celdas. Serverless
factura por los segundos de cómputo realmente consumidos por la consulta/celda, sin el
tiempo muerto de arranque ni de espera entre ejecuciones del mismo notebook. Para un ETL
que corre unos minutos al día, esa diferencia puede ser el factor dominante del costo
mensual — de ahí que DBX-03 pida anotarlo **antes** de seguir: es un dato real para la
lámina de FinOps, no un detalle de configuración.

**📎 Evidencia:** `evidencia/databricks/03_serverless.png`.

---

## DBX-04 · Subir los CSV ⏱️ 10 min

(Sin cambios. El comando y el prefijo `dbfs:` obligatorio son iguales.)

**🧠 Por qué el prefijo `dbfs:` sigue siendo obligatorio sobre un volumen de Unity
Catalog:** el CLI de Databricks mantiene `dbfs:/...` como el esquema de URI genérico
para "sistema de archivos administrado por Databricks", y los volúmenes de Unity
Catalog se exponen *dentro* de ese mismo espacio de nombres bajo `/Volumes/...`. Sin el
prefijo, el CLI interpreta la ruta como una ruta del sistema de archivos local desde
donde corres el comando.

**📎 Evidencia:** `evidencia/databricks/04_archivos.txt`.

---

## DBX-05 · Importar el notebook ⏱️ 10 min

(Mismos pasos. Mismo cambio de `PLATAFORMA = "databricks"` en la celda 2.)

**🧠 Qué pasa por debajo:** `build_notebook.py` genera un único `.ipynb` con una celda de
configuración (celda 2) que define, según el valor de `PLATAFORMA`, las rutas (`RAW`,
`BRONZE`) y la función `T()` que construye nombres de tabla. En Databricks, `T("silver_pedidos")`
devuelve `andina.datos.silver_pedidos` (tres partes); en Fabric devuelve solo
`silver_pedidos` (una parte, porque el Lakehouse ya resuelve el "catálogo" implícito).
Ese único punto de variación es lo que permite mantener **un solo** archivo de
definiciones (`extensiones_spark.py`) para dos plataformas distintas sin bifurcar el
código.

**📎 Evidencia:** `evidencia/databricks/05_notebook.png`.

---

## DBX-06 · Primera ejecución completa ⏱️ 40 min ⭐

(Mismos pasos y misma tabla de cifras esperadas que la versión corta — celdas 5 a 13.)

**🧠 Qué valida cada celda, en una frase:**

| Celda | Qué valida conceptualmente |
|---|---|
| 5 | Que el DDL Delta es válido en este runtime y que Unity Catalog acepta la creación de 19 tablas + 2 vistas con los tipos usados |
| 6 | El **contrato de entrada** (`andina_etl/contracts.py` / `extensiones_spark.py::verificar_contrato`): cabeceras, columnas requeridas, ausencia de columnas extra, antes de que nada se escriba |
| 8 | Las reglas de calidad fila a fila (`rules_spark.py`) y el `MERGE` de Silver, que decide inserción vs actualización por `row_hash` |
| 10 | El recálculo de `gold_venta_neta_diaria` **solo** para los días tocados (no un `TRUNCATE` + reinserción completa) |
| 11 | El modelo estrella (`star.py`/`extensiones_spark.py`): dimensiones estables, hechos reconstruidos por lote |
| 12 | Las compuertas de publicación (`operations.py`): conciliación Silver↔Gold y umbrales, antes de mover `publicacion_actual` |
| 13 | Paridad completa contra DuckDB: la razón de ser de `tests/test_spark_extensiones.py`, pero contra datos reales en vez de sintéticos |

**❌ Catálogo extendido de errores** (añade a la tabla corta):

| Error | Causa | Qué hacer |
|---|---|---|
| `DELTA_UNSUPPORTED_FEATURES_IN_CONFIG` | El catálogo fue creado apuntando a un *metastore* con una versión de protocolo Delta antigua | Normalmente no aplica en un metastore nuevo; si aparece, repórtalo con la versión del runtime |
| La celda 8 tarda mucho más de lo esperado en un clúster chico | El clúster solo tiene 1-2 *workers* pequeños y el `MERGE` en Silver recorre snapshots completos (ver limitación de capacidad en README_ETL.md) | No es un error: es el límite de capacidad conocido y declarado del diseño. Anótalo como dato de rendimiento, no lo fuerces con reintentos |
| `INVALID_PARAMETER_VALUE` al escribir una tabla Delta | Un tipo de columna del CSV no coincide con el esquema declarado (p. ej. un valor no numérico donde se espera `BIGINT`) | Revisa `rules.py`/`rules_spark.py`: estas reglas están pensadas para enviar esa fila a cuarentena, no para que falle el `write`; si falla el `write` en vez de ir a cuarentena, es un hallazgo real de paridad que hay que reportar |

**📎 Evidencia:** exporta el notebook ejecutado con salidas →
`evidencia/databricks/06_primera_corrida.ipynb`. Y captura de la celda 13.

**Cierra:** **E04-01**.

---

## DBX-07 · Quitar el bloqueador de serverless ⏱️ 30 min 🔴

(Mismos pasos de la versión corta: localizar los tres `.cache()` en `PIPELINE` dentro de
`build_notebook.py`, sustituirlos por materialización en tabla *staging*, y el cuarto en
`extensiones_spark.py::verificar_contrato`.)

**🧠 Por qué una tabla *staging* y no, por ejemplo, `.collect()` o `.toPandas()`:**
`.cache()` guarda el DataFrame en la memoria del clúster para que una acción posterior
no recalcule el plan desde el origen. `.collect()`/`.toPandas()` traería **todas** las
filas al driver, lo que no escala y además pierde el tipo Spark DataFrame que el resto
del pipeline necesita. Escribir a una tabla Delta intermedia (`stg_pedidos`) logra el
mismo efecto de "fijar el resultado antes de seguir" pero de forma distribuida: el
*write* ya materializa el resultado en archivos Parquet, y el `spark.table(...)`
posterior lee desde ahí en vez de recalcular el filtro de reglas sobre el CSV original.
Es, además, más robusto que la caché: una caché puede desalojarse de memoria bajo
presión sin aviso; una tabla escrita persiste.

**🧠 Por qué este caso particular (celda 8) es más delicado que los otros tres:** el
comentario de la versión corta ya lo dice — el `.cache()` de `ped_ok` materializa
**antes** de un `MERGE` cuyo *target* (`silver_pedidos`) se lee también como parte del
cálculo de `hash_negocio` para decidir duplicados lógicos. Sin materializar antes del
`MERGE`, Spark podría re-evaluar el plan de `ped_ok` en un punto donde el *target* ya
cambió a mitad de la operación, lo que puede producir resultados inconsistentes entre
ejecuciones del mismo plan lógico (un caso del problema general de leer y escribir la
misma tabla en una sola operación). Por eso la corrección no es "borrar el `.cache()`"
sino "materializar explícitamente en un punto de corte claro".

**📎 Evidencia:** `evidencia/databricks/07_serverless.txt` con el error antes y la
corrida correcta después.

**Avísame del resultado.** Si funciona, lo incorporo al generador con sus pruebas y
cierro E04b en la documentación.

---

## DBX-08 · Los doce escenarios ⏱️ 2–3 h

(Todos los escenarios E04-02 a E04-12 son idénticos a la versión corta: mismos pasos,
mismas cifras esperadas, mismos nombres de archivo de evidencia. Lo que sigue es el
razonamiento detrás de cada uno, para que si el resultado no coincide sepas qué parte
del diseño mirar primero.)

### E04-02 · Segunda carga sin cambios
**Qué prueba de verdad:** la idempotencia vía `row_hash`. Si `insertados` no es `0`, el
hash no está capturando que el contenido es idéntico — revisa si `bronze.py`/
`extensiones_spark.py` normalizan la fila (espacios, mayúsculas) antes de calcular el
hash, de la misma forma en ambas corridas.

### E04-03 · Archivo modificado
**Qué prueba de verdad:** que el `MERGE` actualiza por `row_hash` distinto, no que
reescribe todo. Si `actualizados` sale en 19.270 en vez de 1, el `MERGE` está haciendo
*match* por una clave que siempre es verdadera (revisa la condición `ON`), no por el hash.

### E04-04 · Cabecera alterada
**Qué prueba de verdad:** que el contrato de entrada corre **antes** de Bronze, no
después. Si `bronze_manifest` sí registra una versión nueva a pesar del fallo, el
contrato se está validando tarde (después de escribir, no antes).

### E04-05 · Pago tardío fuera de ventana
**Qué prueba de verdad:** que `PAGO_HUERFANO`/`PEDIDO_EN_CUARENTENA` son una excepción
explícita al watermark (`store.pagos_pendientes`), no que el watermark simplemente no
filtra nada. Para distinguir ambos casos, confirma con otro pago **normal** fuera de
ventana (sin estar huérfano ni en cuarentena) que **sí** se omite.

### E04-06 · Pedido que pasa a inválido
**Qué prueba de verdad:** el mecanismo de retiro (`store.retirar`): un registro que
estuvo bien y ahora viola una regla sale de Silver, no se queda "contaminando" el
cálculo con un valor viejo. Aquí es donde más vale mirar la venta del día antes/después:
si no bajó, el retiro no recalculó Gold.

### E04-07 · Incidencia que se resuelve
**Qué prueba de verdad:** que `calidad_incidencias` es un registro de *estado*, no de
*eventos borrables*: la fila de cuarentena histórica permanece (es evidencia de que algo
pasó), pero el estado de la incidencia cambia a `RESUELTA` cuando se reevalúa el mismo
ID y ya no incumple.

### E04-08 · Fallo entre tablas ⭐
Ya explicado en el recuadro de conceptos arriba (*write-audit-publish*). Lo que tienes
que ver con tus propios ojos aquí es la **divergencia temporal** entre `gold_fact_pedido`
(que ya tiene el `run_id` nuevo) y `v_fact_pedido` (que sigue filtrando por el `run_id`
publicado anterior). Si no ves esa divergencia —si `v_fact_pedido` ya refleja el run
nuevo sin haber corrido la celda 12— significa que la vista no está filtrando por
`publicacion_actual` y el diseño de publicación no está realmente protegiendo nada.

### E04-09 · Compuerta disparada
**Qué prueba de verdad:** que la compuerta de volumen (`PoliticaPublicacion`) se evalúa
**antes** de mover el puntero, no después. El mensaje exacto (`"Volumen menor que mínimo
configurado"`) debe venir acompañado de que `publicacion_actual` *no* cambió — si cambió
a pesar del mensaje de bloqueo, la compuerta solo está *avisando*, no *bloqueando*.

### E04-10 · Recuperación
**Qué prueba de verdad:** el *time travel* de Delta (`DESCRIBE HISTORY` / `RESTORE TABLE
... VERSION AS OF`), que es posible porque el log de transacciones conserva versiones
anteriores en vez de sobrescribir archivos en el sitio. Tras `RESTORE`, el notebook debe
poder reconstruir el estado correcto desde ahí — si no, el pipeline depende de algo que
el `RESTORE` no repuso (por ejemplo, un watermark guardado fuera de la tabla restaurada).

### E04-11 · Claves estables
**Qué prueba de verdad:** que las claves de dimensión (`canal_key`, etc.) se asignan una
vez y se reutilizan, no que se recalculan en cada corrida (lo que rompería cualquier
informe o relación guardada que apunte a esa clave).

### E04-12 · Paridad final
**Qué prueba de verdad:** todo el bloque anterior no dejó el sistema en un estado donde
las cifras agregadas ya no cuadran con la referencia del caso.

**Cierra:** **E04 completo en Databricks.**

---

## DBX-09 · Desplegarlo como job con bundle ⏱️ 45 min

(Mismos pasos, mismo YAML.)

**🧠 Qué es un *bundle* y por qué no es solo "una forma más de crear un job":** un
Databricks Asset Bundle es una definición declarativa (YAML) de recursos del workspace
—jobs, pipelines, permisos— que vive en control de versiones y se despliega con
`bundle deploy`. La alternativa (crear el job a mano en la UI) no deja rastro en Git: si
alguien cambia el *schedule* o el *cluster* desde la UI, no hay *diff* que lo muestre.
Con el bundle, cualquier cambio al job pasa por el mismo flujo de revisión que el código.

**🧠 Por qué `performance_target: STANDARD` y no omitir el campo:** en Jobs Serverless,
omitir `performance_target` puede usar un valor por defecto distinto según la versión de
la plataforma; ser explícito con `STANDARD` deja constancia escrita de la decisión de
costo (lote nocturno, sin SLA de latencia) en el propio YAML, no en una conversación que
se olvida.

**❌ Catálogo extendido de errores**

| Error | Causa | Qué hacer |
|---|---|---|
| `bundle validate` falla con `permission denied` sobre el notebook | El `notebook_path` no coincide con donde lo importaste en DBX-05 | Confirma la ruta exacta con `databricks workspace list /Users/TU_USUARIO` |
| El job corre pero nunca termina | El notebook quedó con una celda que espera interacción (poco común, pero puede pasar si alguien dejó un `input()` o un *widget* sin valor por defecto) | Revisa que todas las celdas corran sin intervención manual, como en DBX-06 |
| `bundle deploy` crea un job duplicado cada vez | El `target` cambió entre despliegues, o el nombre del job no es estable | Usa siempre el mismo `--target dev` y el mismo `name:` en el YAML |

**📎 Evidencia:** `evidencia/databricks/09_bundle.txt`.

---

## DBX-10 · Gobierno: permisos y enmascaramiento ⏱️ 30 min

(Mismo SQL que la versión corta.)

**🧠 Qué es una función de enmascaramiento de columna en Unity Catalog:** no es una vista
que oculta la columna — la tabla física sigue teniendo el documento completo. Es una
función SQL registrada que Unity Catalog **inyecta automáticamente** en cualquier
consulta sobre esa columna, evaluada según la identidad de quien consulta
(`is_account_group_member(...)`). Esto significa que el enmascaramiento aplica igual si
la consulta viene de un notebook, de Power BI o de una herramienta de BI externa: el
control vive en el catálogo, no en cada aplicación que lo consume — a diferencia de
enmascarar en la capa de reporte, que hay que repetir en cada herramienta.

**📎 Evidencia:** `evidencia/databricks/10_gobierno.txt`.

---

## DBX-11 · Linaje y costo ⏱️ 20 min

(Mismo SQL que la versión corta.)

**🧠 De dónde sale el linaje automáticamente:** Unity Catalog captura `table_lineage` sin
que el código del notebook haga nada especial para declararlo — lo infiere del plan de
ejecución de Spark cada vez que una consulta lee de una tabla y escribe en otra. Por eso
el linaje de `gold_fact_pedido` muestra como origen `silver_pedidos`, aunque el notebook
nunca llamó a una API de linaje explícitamente.

**🧠 Qué son las tablas `system.*`:** son el *metastore* de sistema que Databricks
expone como tablas Delta normales, consultables con SQL (facturación, auditoría,
linaje, uso de cómputo). Es la misma idea que `information_schema` en un motor
relacional, pero cubriendo cuenta/plataforma completa, no solo un esquema.

**📎 Evidencia:** `evidencia/databricks/11_linaje_costo.txt`.

---

## DBX-12 · Apagar todo ⏱️ 5 min

(Sin cambios.)

**📎 Evidencia:** `evidencia/databricks/12_apagado.png`.

---

## Glosario

| Término | Qué significa aquí |
|---|---|
| **Metastore** | El catálogo central de Unity Catalog que agrupa catálogos/esquemas/tablas y puede compartirse entre varios workspaces de una cuenta |
| **Catálogo / esquema / tabla** | Las tres partes del nombre `andina.datos.silver_pedidos`: nivel más alto, agrupación intermedia, objeto final |
| **Volumen** | Almacenamiento no tabular (archivos) gobernado por Unity Catalog, `MANAGED` (ubicación elegida por la plataforma) o `EXTERNAL` (ubicación que tú controlas) |
| **DBU** | Databricks Unit: unidad de facturación de cómputo, no una hora de máquina |
| **Serverless (Jobs/SQL)** | Cómputo administrado por la plataforma, facturado por uso real, sin control directo sobre el clúster subyacente |
| **Bundle (DAB)** | Definición declarativa en YAML de recursos de Databricks (jobs, pipelines) versionable en Git |
| **`_delta_log`** | El log de transacciones de una tabla Delta; permite *time travel* (`DESCRIBE HISTORY`, `RESTORE TABLE`) |
| **`run_id` / puntero de publicación** | El mecanismo de este proyecto para simular una transacción entre tablas que Delta no ofrece de forma nativa |
| **Lineage (`system.access.table_lineage`)** | Relación origen→destino entre tablas, capturada automáticamente a partir de los planes de ejecución de Spark |

## Preguntas frecuentes de este bloque

**¿Por qué el notebook crea 19 tablas y no, por ejemplo, 4 (una por CSV)?**
Porque además de las cuatro tablas Silver (clientes, pedidos, pagos, tickets) existen las
de control (cuarentena, incidencias, watermark, manifiesto de bronze) y el modelo
estrella Gold completo (dimensiones + hechos). Ver la lista exacta en
[README_ETL.md](../../README_ETL.md#modelo-y-transacción).

**¿Por qué serverless "no cobra en reposo" y un clúster clásico sí, si ambos son
cómputo en la nube de todas formas?**
Un clúster clásico reserva máquinas virtuales completas mientras esté `RUNNING`, aunque
nadie ejecute código en ese momento (el *auto-termination* solo actúa tras un periodo de
inactividad configurado, por defecto no inmediato). Serverless no reserva una máquina
para ti: ejecuta tu consulta sobre un pool compartido y factura por el tiempo de cómputo
real de esa ejecución.

**Si DBX-07 no funciona, ¿el proyecto queda roto?**
No. El notebook funciona igual en un clúster clásico (donde `.cache()` sí está
disponible); DBX-07 es específicamente para habilitar **serverless**, que es el cómputo
recomendado por costo, no un requisito del diseño.

**¿Por qué el escenario E04-08 se marca como "el más importante" y no, por ejemplo,
E04-06?**
Porque es el único escenario que hace *visible* la diferencia de fondo entre el flujo
local (una transacción DuckDB real) y el flujo Delta (un puntero de publicación). Los
demás escenarios prueban reglas de negocio que también existen en DuckDB; E04-08 prueba
el mecanismo que existe **solo** porque Delta no tiene transacción entre tablas.

## Para profundizar (documentación oficial)

- Unity Catalog — conceptos de catálogo, esquema y volumen: <https://docs.databricks.com/>
- Delta Lake — transacciones, `_delta_log` y *time travel*: <https://docs.delta.io/>
- Databricks Asset Bundles: <https://docs.databricks.com/dev-tools/bundles/>
- Tablas de sistema (`system.access`, `system.billing`): <https://docs.databricks.com/admin/system-tables/>
