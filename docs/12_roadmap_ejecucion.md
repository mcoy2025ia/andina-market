# Roadmap de ejecución: lo que necesito que hagas tú

**Corte:** 1 de noviembre de 2026. Este documento cierra la pregunta «¿qué falta y
quién lo hace?». Todo lo que podía hacerse sin credenciales de producción está hecho
(IA-R01 a IA-R05). Lo que queda necesita **tus cuentas**: Databricks, Fabric, Power BI
y un motor T-SQL.

Para cada tarea: **qué haces**, **el comando exacto**, **qué debe salir**, **qué
evidencia capturas** y **qué desbloquea**. Cuando me devuelvas la evidencia, yo
actualizo documentación y estados; eso no lo hagas tú.

> **Regla que no se negocia.** Si una tarea no da el resultado esperado, **no la marques
> como hecha**. Un «casi» en este proyecto se convierte en una afirmación falsa en la
> sustentación. Anota el error y seguimos.

---

## 0. Lo que detecté en tu entorno

Comprobado hoy, sin seleccionar ningún perfil ni tocar tus workspaces:

| Hallazgo | Estado | Acción |
|---|---|---|
| Databricks CLI v1.23.0 instalado | ✅ Sirve | Ninguna |
| Único perfil en `.databrickscfg`, llamado con una **URL de notebook pegada** | ❌ Marca `Valid: NO` | **D0**: crear un perfil limpio |
| Host del workspace | `https://dbc-ebd35512-279a.cloud.databricks.com` | Se usa en D0 |
| Java 17 y Python 3.11 locales | ✅ Spark corre en tu máquina | Ninguna |
| Cuenta Fabric / Power BI | Declarada por ti, **no verificada** por mí | **F0** la confirma |
| Motor T-SQL (SQL Server) | **No lo mencionaste** | Decisión **DEC-3** |

El perfil inválido es lo primero: sin eso ningún comando de Databricks funciona.

---

## 1. Tres decisiones antes de tocar nada

### DEC-1 · ¿Subes los datos reales a la nube? ⚠️

`data/original/*.csv` contiene **documentos de identidad y texto escrito por clientes**.
Subirlos a un workspace en la nube es una decisión de privacidad, no un paso técnico.
No la tomo por ti.

| Opción | Qué valida | Qué no valida |
|---|---|---|
| **A · Solo sintéticos** (recomendado para empezar) | Todos los mecanismos: contratos, cuarentena, idempotencia, conciliación, publicación, MERGE, recuperación | Las cifras del caso (6.040 / 19.270 / 20.124 / 7.925 / COP 14.177.333.600) |
| **B · Datos reales** | Todo, incluidas las cifras | Exige que tengas autorización sobre esos datos y un workspace con el control de acceso adecuado |

```bash
# Opción A: genera los cuatro CSV sintéticos (cada tipo de error sembrado a propósito)
python scripts/generar_csv_sinteticos.py --out .local/sinteticos
```

**Mi recomendación:** empieza por A. Valida toda la mecánica con sintéticos, y solo si
después quieres cerrar E04-01 y E04-12 con las cifras del caso, repite con B en un
workspace con acceso restringido. Casi todo el valor está en A.

### DEC-2 · ¿Cuál es tu plataforma piloto?

**Validar Fabric no acredita Databricks, ni al revés.** Elige **una** para ir a fondo;
la otra queda como comparación. Si tu objetivo es la prueba técnica, el criterio es:

- **Fabric** si quieres cerrar también Power BI y DAX en el mismo sitio (E03 + E04 de
  una vez) y si te interesa el detalle de que **Warehouse sí soporta transacción
  multi-tabla**, que haría innecesario el patrón del puntero de run.
- **Databricks** si quieres demostrar gobierno fino (Unity Catalog, *row filters*,
  linaje por columna) y el flujo serverless completo.

**Mi recomendación:** **Fabric como piloto principal** —cierra tres pendientes a la vez
(E03, E04 y parte de E02 vía Warehouse)— y **Databricks como validación secundaria** del
bloque D, que es más rápido de lo que parece.

### DEC-3 · ¿Qué motor T-SQL usas para E01 y E02?

No mencionaste SQL Server. Opciones, de menor a mayor fricción:

| Opción | Sirve para | Límite |
|---|---|---|
| **Fabric Warehouse** | Ejecutar el DDL y las consultas T-SQL, conexión desde Power BI | No es SQL Server: no hay planes de ejecución idénticos, ni `IDENTITY_INSERT` con la misma semántica. Para la **optimización** (E02) no vale |
| **Azure SQL Database** (nivel básico) | E01 y E02 casi completos | Costo por hora; hay que apagarla |
| **SQL Server en Docker local** | E01 y E02 completos, gratis | Requiere Docker y ~2 GB de RAM |

**Mi recomendación:** **SQL Server en Docker** para E01 y E02. Es gratis, es el motor
real, y la medición de optimización solo tiene sentido ahí. Fabric Warehouse lo
complementa pero no lo sustituye.

---

## 2. Vía rápida: si solo tienes un día

Si el tiempo es poco, este es el orden que **más afirmaciones cierra por hora**:

| Orden | Tarea | Tiempo | Qué cierra |
|---|---|---|---|
| 1 | D0 + D1 · perfil y catálogo | 20 min | Desbloquea todo Databricks |
| 2 | **E04b** · quitar los `.cache()` | 30 min | Bloqueador conocido |
| 3 | D3–D5 · subir, importar y ejecutar el notebook | 60 min | **E04-01 y E04-02**, lo más valioso |
| 4 | P1–P3 · modelo y medidas en Power BI | 90 min | **E03**, la afirmación más floja hoy |
| 5 | D6 · segunda carga y escenarios | 45 min | E04-03 a E04-07 |

Con eso pasas de «escrito» a «ejecutado» en los dos puntos que más se preguntan en una
sustentación: el notebook Delta y las medidas DAX.

---

## 3. Bloque D · Databricks

> Guía: `databricks-core`, `databricks-serverless`, `databricks-unity-catalog` y
> `databricks-dabs`. **Nunca selecciono un perfil por ti**: todos los comandos llevan
> `--profile`.

### D0 · Crear un perfil válido  ⏱️ 10 min

Tu perfil actual tiene como **nombre** una URL de notebook pegada, y está inválido.

```bash
# Crea un perfil limpio por OAuth. Abre el navegador y pide confirmación.
databricks auth login \
  --host https://dbc-ebd35512-279a.cloud.databricks.com \
  --profile finanzauto

# Verifica
databricks auth profiles
databricks current-user me --profile finanzauto
```

**Esperado:** `finanzauto` aparece con `Valid: YES` y `current-user me` devuelve tu
usuario.
**Evidencia:** salida de `databricks auth profiles` (sin tokens).
**Desbloquea:** todo el bloque D.

> Si falla, bórrame el perfil viejo: edita `~/.databrickscfg` y elimina la sección cuyo
> nombre es la URL larga. No borres el archivo entero.

### D1 · Crear catálogo, esquema y volumen  ⏱️ 10 min

```bash
databricks catalogs create --json '{"name": "andina"}' --profile finanzauto
databricks schemas create  --json '{"name": "datos", "catalog_name": "andina"}' --profile finanzauto
databricks volumes create  --json '{
  "catalog_name": "andina", "schema_name": "datos",
  "name": "raw", "volume_type": "MANAGED"}' --profile finanzauto

databricks volumes list andina.datos --profile finanzauto
```

**Esperado:** el volumen `andina.datos.raw` aparece en la lista.
**Si falla con `PERMISSION_DENIED`:** no eres administrador del metastore. Usa un
catálogo que ya exista y ajusta `T()` en la celda 1 del notebook.
**Evidencia:** salida de `volumes list`.

### D2 · Confirmar que hay serverless  ⏱️ 5 min

En la UI: **Compute → Serverless**. Si tu workspace no tiene serverless habilitado, todo
el bloque corre igual en cómputo clásico, pero anótalo: cambia la recomendación de
costo.
**Evidencia:** captura de la página de Compute.

### D3 · Subir los CSV al volumen  ⏱️ 10 min

```bash
# DEC-1 opción A (sintéticos)
python scripts/generar_csv_sinteticos.py --out .local/sinteticos
databricks fs cp -r --overwrite .local/sinteticos \
  dbfs:/Volumes/andina/datos/raw --profile finanzauto

# DEC-1 opción B (datos reales) — solo si decidiste subirlos
databricks fs cp -r --overwrite data/original \
  dbfs:/Volumes/andina/datos/raw --profile finanzauto

databricks fs ls dbfs:/Volumes/andina/datos/raw --profile finanzauto
```

**Ojo:** el prefijo `dbfs:` es obligatorio aunque sea un volumen de Unity Catalog. Sin
él, el CLI lo trata como ruta local y falla con «no such directory».
**Esperado:** los cuatro CSV listados.
**Evidencia:** salida de `fs ls`.

### D4 · Corregir el bloqueador de serverless (E04b)  ⏱️ 30 min  🔴

**Este es el único cambio de código que te pido**, y te lo pido a ti porque solo se
puede verificar con la plataforma delante.

El notebook usa `.cache()` en cuatro puntos y **Databricks serverless no lo admite**.
Quitarlo sin más no basta: en la celda de pedidos ese `.cache()` además materializa
antes del `MERGE`, y el origen de ese `MERGE` lee la misma tabla que escribe.

1. Ejecuta el notebook tal cual en **cómputo clásico** primero (D5). Si pasa, ya tienes
   E04-01 cerrado en clásico.
2. Después, para serverless, edita `src/shared/spark/build_notebook.py` y sustituye
   cada `X = X.cache()` por una materialización en tabla de staging:

```python
# en vez de:  ped_ok = ped_ok.cache()
ped_ok.write.mode("overwrite").saveAsTable(T("stg_pedidos"))
ped_ok = spark.table(T("stg_pedidos"))
```

3. Regenera y vuelve a importar: `python src/shared/spark/build_notebook.py`

**Esperado:** el notebook completa en serverless sin `AnalysisException` por `.cache()`.
**Evidencia:** la traza del error antes, y la corrida completa después.
**Avísame del resultado**: si funciona, lo incorporo al generador y actualizo las
pruebas.

### D5 · Importar y ejecutar el notebook  ⏱️ 40 min

```bash
databricks workspace import /Users/TU_USUARIO/andina_etl_spark \
  --file fabric/notebooks/andina_etl_spark.ipynb \
  --format JUPYTER --profile finanzauto
```

En la UI, antes de ejecutar, **celda 1**: cambia `PLATAFORMA = "databricks"`. Verifica
que `RAW` y `BRONZE` apunten a `/Volumes/andina/datos/...`.

Ejecuta **todas** las celdas en orden.

**Esperado (opción A, sintéticos):** la celda 12 compara contra las constantes del caso
y **dará diferente** — es correcto, esas constantes son para los datos reales. Lo que
debe cumplirse: ninguna celda falla, la estrella concilia (celda 10) y la publicación
queda VALIDADO (celda 11) con venta neta **350.000**.
**Esperado (opción B, reales):** la celda 12 imprime `OK` en las cinco líneas.
**Evidencia:** salida de las celdas 9, 10, 11 y 12. Exporta el notebook ejecutado.
**Cierra:** **E04-01**.

### D6 · Los doce escenarios  ⏱️ 2–3 h

La tabla completa, con resultado esperado y evidencia, está en
[08_traslado_delta.md](08_traslado_delta.md#4-escenarios-para-e04). Resumen de lo que
tienes que provocar:

| Escenario | Cómo lo provocas | Qué debe pasar |
|---|---|---|
| E04-02 Segunda carga | Reejecutar todo sin cambiar nada | 0 insertados, 0 actualizados; Bronze no re-aterriza |
| E04-03 Archivo modificado | Cambiar un valor en un CSV y volver a subir | Solo cambian las filas con hash distinto |
| E04-04 Cabecera alterada | Renombrar una columna en el CSV | **Falla en la celda 5**, antes de tocar Bronze |
| E04-05 Pago tardío | Añadir un pago cuyo pedido ya está cargado, con `fecha_carga` vieja | El pago sale de cuarentena |
| E04-06 Pedido inválido | Poner `valor_bruto` negativo a un pedido ya cargado | Sale de Silver, su día se recalcula, la venta baja |
| E04-07 Incidencia resuelta | Corregir el dato del escenario anterior | Pasa a `RESUELTA` sin borrar la cuarentena |
| E04-08 Fallo entre tablas | Interrumpir el notebook entre las celdas 10 y 11 | `publicacion_actual` **no** se mueve; `v_fact_*` siguen en el run anterior |
| E04-09 Compuerta | `POLITICA = PoliticaPublicacion(min_pedidos=999999)` en la celda 11 | `PublicacionBloqueada`; hechos escritos pero no publicados |
| E04-10 Recuperación | `RESTORE TABLE andina.datos.silver_pedidos TO VERSION AS OF N` | La tabla vuelve y la reejecución cuadra |
| E04-11 Claves estables | Comparar `gold_dim_canal` entre corridas | Las claves no cambian |
| E04-12 Paridad | Solo con datos reales | Cifras iguales a las locales |

**Evidencia por escenario:** la salida de la celda relevante más, donde aplique,
`DESCRIBE HISTORY andina.datos.<tabla> LIMIT 5`.
**Cierra:** **E04 completo**.

### D7 · Convertirlo en un job con bundle  ⏱️ 45 min  *(opcional pero recomendado)*

Esto cierra parte de E05 y demuestra despliegue reproducible.

```bash
databricks bundle init --profile finanzauto      # elige la plantilla default-python
databricks bundle validate --strict --target dev --profile finanzauto
databricks bundle deploy --target dev --profile finanzauto
databricks bundle run <nombre_job> --target dev --profile finanzauto
```

En el YAML del job:
- **no** pongas `job_clusters`, `new_cluster` ni `node_type_id`: sin bloque de cómputo,
  la tarea corre en **serverless**, que es el predeterminado;
- `performance_target: STANDARD` — es un lote nocturno sin compromiso de latencia, y
  STANDARD cuesta menos; `PERFORMANCE_OPTIMIZED` solo si alguien espera el resultado;
- etiqueta el job (`tags`), o después no podrás repartir el costo por área.

**Evidencia:** `databricks bundle validate` en verde y una ejecución correcta.
**Cierra:** parte de **E05**.

### D8 · Gobierno y costo  ⏱️ 30 min

```sql
-- Permisos: concede en el securable más estrecho que funcione
GRANT USE CATALOG ON CATALOG andina TO `<tu_grupo>`;
GRANT USE SCHEMA  ON SCHEMA  andina.datos TO `<tu_grupo>`;
GRANT SELECT      ON SCHEMA  andina.datos TO `<tu_grupo>`;
SHOW GRANTS ON TABLE andina.datos.gold_fact_pedido;

-- Enmascarar el documento de identidad (si subiste datos reales)
-- Requiere una función de máscara; ver references de Unity Catalog.

-- Costo por carga, una vez el job haya corrido unos días
SELECT sku_name, SUM(usage_quantity) AS dbus
FROM system.billing.usage
WHERE usage_date >= current_date() - 30
GROUP BY sku_name ORDER BY dbus DESC;

-- Linaje: de dónde sale cada tabla
SELECT source_table_full_name, target_table_full_name
FROM system.access.table_lineage
WHERE target_table_full_name LIKE 'andina.datos.gold%'
  AND event_date >= current_date() - 7;
```

**Evidencia:** salida de `SHOW GRANTS` y de las dos consultas de sistema.
**Cierra:** la lámina 19 del deck deja de ser teórica.

---

## 4. Bloque F · Microsoft Fabric

### F0 · Confirmar capacidad y workspace  ⏱️ 15 min

1. Confirma qué **capacidad** tienes (F2, F64, prueba gratuita…) y en qué región.
2. Crea un workspace y **asígnalo a esa capacidad**.
3. Anota si puedes **pausar** la capacidad: es la palanca de costo más importante.

**Evidencia:** captura de la configuración del workspace mostrando la capacidad.
**Me sirve para:** cerrar la lámina 22 con tu modelo de costo real, no genérico.

### F1 · Crear el Lakehouse y subir los archivos  ⏱️ 20 min

1. **Nuevo → Lakehouse**, nómbralo `andina`.
2. En **Files**, crea la carpeta `andina/raw`.
3. Sube los cuatro CSV (sintéticos o reales, según DEC-1).

**Esperado:** los cuatro archivos en `Files/andina/raw/`.
**Evidencia:** captura del explorador de archivos.

### F2 · Importar y ejecutar el notebook  ⏱️ 45 min

1. **Importar notebook** → `fabric/notebooks/andina_etl_spark.ipynb`.
2. **Adjunta el Lakehouse** `andina` al notebook (sin esto, `Files/...` no resuelve).
3. Celda 1: `PLATAFORMA = "fabric"` (ya es el valor por defecto).
4. Ejecuta todas las celdas.

**Esperado:** igual que D5.
**Evidencia:** notebook ejecutado con salidas; exporta a `.ipynb` o PDF.
**Cierra:** **E04-01** en Fabric.

### F3 · Los doce escenarios en Fabric  ⏱️ 2–3 h

Misma tabla que D6. **Validar Fabric no acredita Databricks**: si haces los dos, dilo
por separado.

### F4 · La prueba que solo Fabric permite  ⏱️ 45 min  ⭐

Esta es la más interesante del bloque y no existe en Databricks.

**Hipótesis a verificar:** *Fabric Warehouse soporta transacciones multi-tabla en
T-SQL*. Si es cierto, el patrón de `run_id` + puntero de publicación **sobraría** en
Warehouse, porque se podría usar una transacción real como en DuckDB.

1. Crea un **Warehouse** en el mismo workspace.
2. Ejecuta `sqlserver/ddl_tsql.sql` adaptando lo que Warehouse no soporte (anota qué).
3. Prueba una transacción que toque dos tablas y haz `ROLLBACK`:

```sql
BEGIN TRANSACTION;
  INSERT INTO gold.fact_pedido (...) VALUES (...);
  INSERT INTO gold.fact_pago   (...) VALUES (...);
ROLLBACK;
-- Ninguna de las dos filas debe quedar
SELECT COUNT(*) FROM gold.fact_pedido;
SELECT COUNT(*) FROM gold.fact_pago;
```

**Esperado:** si el rollback deshace **ambas**, la hipótesis se confirma.
**Evidencia:** el script y sus resultados.
**Cierra:** convierte la lámina 18 del deck en un argumento verificado y te da una
respuesta fuerte a «¿por qué Fabric y no Databricks?».

### F5 · Modelo semántico Direct Lake  ⏱️ 30 min

Desde el Lakehouse, crea un **modelo semántico** sobre las tablas `gold_*`.
**Evidencia:** captura del modelo con las relaciones.
**Desbloquea:** el bloque P sin necesidad de importar datos.

---

## 5. Bloque P · Power BI y DAX (E03)

> **Este es el pendiente con la afirmación más floja hoy.** Las medidas están escritas
> y revisadas, pero **nunca se han ejecutado en un motor DAX**. Cerrarlo es barato y
> vale mucho.

### P1 · Construir o conectar el modelo  ⏱️ 30 min

- **Si hiciste F5:** conecta Power BI al modelo semántico de Fabric.
- **Si no:** Power BI Desktop → conecta a Databricks (`andina.datos`) o importa las
  tablas `gold_*`.

Relaciones necesarias:
`fact_pedido[fecha_key] → dim_fecha[fecha_key]` (muchos a uno), y lo mismo para
`canal_key`, `categoria_key` y `cliente_key`.

### P2 · Marcar la tabla de fechas  ⏱️ 10 min  🔴

**Sin esto, `DATEADD` falla o devuelve resultados erróneos.** En el modelo: selecciona
`dim_fecha`, **Marcar como tabla de fechas**, columna `fecha`.

También necesitas la columna calculada que limita el período comparable:

```dax
tiene_datos =
VAR ultima = CALCULATE(MAX(fact_pedido[fecha_key]), ALL(fact_pedido))
RETURN dim_fecha[fecha_key] <= ultima
```

**Por qué importa:** el calendario cubre **años completos** porque `DATEADD` lo exige,
pero los datos terminan el 30-09-2026. Sin este límite, con 2026 seleccionado
compararía 9 meses contra 12 y la variación saldría **+20,2 %** en vez de **+98,9 %**.

### P3 · Instalar las medidas y verificar  ⏱️ 45 min

Copia las cinco medidas de `fabric/semantic_model/medidas.dax`. Luego **verifica contra
estos valores**, que salen de SQL sobre Silver:

| Mes | Venta neta | Pedidos | Ticket | Año anterior | Variación |
|---|---:|---:|---:|---:|---:|
| 2026-01 | 948.592.900 | 1.085 | 874.279 | 113.198.600 | +737,99 % |
| 2026-02 | 822.651.100 | 982 | 837.730 | 213.279.700 | +285,71 % |
| 2026-03 | 926.711.300 | 1.048 | 884.267 | 320.529.800 | +189,12 % |
| 2026-06 | 864.946.200 | 1.013 | 853.846 | 455.631.200 | +89,83 % |
| 2026-09 | 795.114.800 | 901 | 882.480 | 648.367.500 | +22,63 % |
| 2026 ene–sep | 7.739.061.400 | | | 3.891.305.400 | +98,88 % |
| **Total período** | **14.177.333.600** | **16.855** | | | |

> Estos valores solo aplican con **datos reales** (DEC-1 opción B).

**Pruebas adicionales que debes hacer:**

| Prueba | Esperado |
|---|---|
| Seleccionar **2025** | Variación **vacía**, no 0 % |
| Seleccionar el **año 2026** completo | +98,88 % (si sale +20,2 %, `tiene_datos` no está aplicada) |
| Un mes **sin ventas** en un canal | Cero, no la fila desaparecida |
| Filtrar un **canal** | Las cinco medidas responden al filtro |

**Evidencia:** captura de una matriz mes × medida con los valores, y captura de 2025 en
vacío.
**Cierra:** **E03**. Y permite cambiar en todos los documentos «DAX escrito» por «DAX
ejecutado y verificado contra N valores».

### P4 · Reporte y conexión de solo lectura  ⏱️ 30 min  *(opcional)*

Construye una página con venta mensual por canal y la variación. Confirma que el
usuario de conexión es de **solo lectura**.
**Evidencia:** captura del reporte y del rol usado.

---

## 6. Bloque S · T-SQL, modelo y optimización (E01 y E02)

> Según DEC-3. Si eliges Docker, aquí está todo.

### S0 · Levantar SQL Server  ⏱️ 20 min

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=<una_clave_fuerte>" \
  -p 1433:1433 --name sqlserver-andina -d mcr.microsoft.com/mssql/server:2022-latest
```

**Evidencia:** `docker ps` mostrando el contenedor.
**No pongas esa clave en ningún archivo del repositorio.**

### S1 · Ejecutar el DDL  ⏱️ 20 min

Ejecuta `sqlserver/ddl_tsql.sql`. Crea tres esquemas (`silver`, `control`, `gold`), las
tablas, las vistas y los índices.

**Esperado:** se ejecuta sin errores.
**Si falla:** anótame el error exacto y la línea. El DDL **nunca se ha ejecutado**;
encontrar errores aquí es el objetivo, no un fracaso.
**Evidencia:** salida del script y `SELECT name FROM sys.tables ORDER BY name`.
**Cierra:** la mitad de **E01**.

### S2 · Cargar el modelo estrella  ⏱️ 30 min

```bash
pip install pyodbc
export DWH_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=andina;UID=...;PWD=...;TrustServerCertificate=yes"

# Primero el plan, sin escribir nada
python scripts/cargar_modelo_sqlserver.py --db data/warehouse.duckdb

# Después la carga, que exige confirmar explícitamente que es un entorno de pruebas
python scripts/cargar_modelo_sqlserver.py --db data/warehouse.duckdb --aplicar --entorno-pruebas
```

**Esperado:** los conteos en SQL Server coinciden con los locales: `fact_pedido` 19.270,
`fact_pago` 20.124, `fact_ticket` 2.125, `fact_venta_neta_diaria` 7.925.
**Verifica también los tipos monetarios:** que `BIGINT` haya llegado como `BIGINT` y no
se haya convertido en algo con decimales.
**Evidencia:** conteos y `SELECT SUM(venta_neta) FROM gold.fact_venta_neta_diaria`
(debe dar 14.177.333.600).
**Cierra:** **E01**.

### S3 · Ejecutar las consultas de venta y recompra  ⏱️ 30 min

Ejecuta `sqlserver/01_ventas_recompra.sql` y **compara fila a fila** contra el resultado
de DuckDB:

```bash
python -c "import duckdb;print(duckdb.connect('data/warehouse.duckdb',read_only=True).execute(open('duckdb/01_ventas_recompra.sql',encoding='utf-8').read().split(';')[0]).fetchall()[:5])"
```

**Esperado:** mismas filas, mismos valores. Presta atención a los **meses sin ventas**:
deben aparecer con cero, no faltar.
**Evidencia:** ambos resultados lado a lado.
**Cierra:** la mitad de **E02**.

### S4 · Medir la optimización  ⏱️ 60 min  ⭐

Es la prueba que convierte el experimento SQLite en evidencia real.

1. Genera datos: cuantos más, mejor (500.000 pedidos ya muestra el efecto).
2. Ejecuta la consulta **original** del enunciado con `SET STATISTICS IO, TIME ON` y
   captura el plan de ejecución.
3. Ejecuta `sqlserver/optimizacion/02_optimizacion.sql` (reescrita + índices) igual.
4. Compara: tiempo, lecturas lógicas y el plan.

**Esperado (hipótesis a confirmar):** el `CAST(... AS VARCHAR(20))` en el cruce con
tickets provoca un *scan* en vez de un *seek*. En SQLite, quitarlo solo bajó de 7,28 s a
0,06 s.
**Evidencia:** los dos planes de ejecución y las estadísticas de IO/tiempo.
**Cierra:** **E02** y convierte el «no medido en SQL Server» en un hecho.

### S5 · Conexión ODBC de solo lectura  ⏱️ 20 min

Crea un usuario con permisos de solo lectura sobre `gold` y prueba
`src/shared/reporte_ventas.py` contra él.
**Esperado:** el reporte consulta con parámetros (`?`) y devuelve la venta del día.
**Evidencia:** salida del reporte. **No publiques la cadena de conexión.**

---

## 7. Bloque O · Operación (E05)

| ID | Tarea | Tiempo | Cierra |
|---|---|---|---|
| O1 | Proteger la rama `main` en GitHub: exigir PR, revisor y que la CI pase | 15 min | Parte de E05 |
| O2 | Programar el job (D7) con una ejecución diaria | 15 min | Programación |
| O3 | Configurar notificación de fallo al canal que autorices | 20 min | Alertas |
| O4 | Medir cuánto tarda la restauración de una tabla (`RESTORE`) y anotarlo | 30 min | Base para RPO/RTO |
| O5 | Revisar `system.billing.usage` tras una semana y calcular el costo por carga | 20 min | Unit economics |

**Evidencia O1:** captura de las reglas de protección de rama.
**Evidencia O4:** el tiempo medido. Es el primer dato real para acordar RPO y RTO (U08).

---

## 8. Bloque I · IA (E06) y decisiones

### I1 · Revisar las 34 etiquetas  ⏱️ 2 h  🔴 **U05 — bloquea todo el bloque de IA**

```bash
# La plantilla ya existe en el repositorio
start docs/revision_etiquetas_34.csv
```

Para cada una de las 34 filas, completa `anotador_1`, `anotador_2`, `decision_final`,
`motivo` y `particion`. La guía está en [REVISION_HUMANA_IA.md](REVISION_HUMANA_IA.md).

**Dos anotadores de verdad.** Si solo hay una persona, que sea una persona distinta de
quien escribió la propuesta, o anótalo como limitación. **No uses otra IA.**

```bash
# Auditar el formato y medir el acuerdo entre anotadores
python scripts/revision_etiquetas.py auditar docs/revision_etiquetas_34.csv

# Importar las decisiones (se niega si falta algo)
python scripts/importar_etiquetas.py revision --db data/warehouse.duckdb \
  --archivo docs/revision_etiquetas_34.csv --version rev-2026-11-XX
python scripts/cargar_datos.py     # reconstruye los hechos con las etiquetas
```

**Esperado:** `estado: VALIDADO_FORMATO`, sin fugas, y después
`gold.fact_ticket.tipo_caso` poblado con `clasificacion_estado = 'REVISADA'`.
**Cierra:** **U05**, y desbloquea E06.

### I2 · Muestra reservada real  ⏱️ según disponibilidad  *(U06)*

Tickets **nuevos**, autorizados, representativos y etiquetados por personas. No
reutilices los 34 textos.

```bash
python scripts/clasificar_tickets.py reservada --metodo reglas \
  --muestra <tu_csv> --procedencia "descríbela aquí"
```

**Cierra:** **E06** parcialmente. Sin esto, cualquier cifra de desempeño sigue siendo
sintética.

### Decisiones que solo puedes tomar tú

| ID | Decisión | Por qué me bloquea |
|---|---|---|
| U01 | Fecha y forma de entrega | Portada y fechas de los documentos |
| U02 | Acceso del evaluador: ¿ZIP o repositorio? | Instrucciones de revisión |
| U03 | Pesos enteros o centavos; devoluciones; categorías gobernadas | Tipos en Silver, Gold, DDL y DAX **a la vez** |
| U04 | Contrato de fuente: ¿snapshot o incremento? ¿Qué significa una ausencia? | Sin esto no se pueden habilitar bajas |
| U07 | Destinatarios, canal y horario del reporte | El transporte existe y se niega a enviar sin esto |
| U08 | Umbrales, frescura, RPO y RTO | Las compuertas están vacías a propósito |
| U09 | Presupuesto del entorno | Límite de consumo |
| U10 | Rotación de credenciales expuestas, si aplica | Higiene |

---

## 9. Roadmap por días

### Día 1 · Databricks (4 h)
D0 → D1 → D2 → D3 → D5 → D6 (escenarios 02 a 07).
**Cierra:** E04 en Databricks, salvo serverless.

### Día 2 · Power BI (3 h) ⭐ *el de mayor retorno*
P1 → P2 → P3 → P4.
**Cierra:** E03. Deja de ser cierto que «DAX nunca se ejecutó».

### Día 3 · Fabric (4 h)
F0 → F1 → F2 → F3 → **F4** (la prueba de transacción multi-tabla) → F5.
**Cierra:** E04 en Fabric y un argumento de arquitectura verificado.

### Día 4 · SQL Server (4 h)
S0 → S1 → S2 → S3 → **S4** (la medición de optimización) → S5.
**Cierra:** E01 y E02.

### Día 5 · Operación, IA y cierre (4 h)
D4 (serverless) → D7 (bundle) → D8 (gobierno) → O1–O5 → I1 (las 34 etiquetas).
**Cierra:** E05 parcial, E04b y U05.

**Si solo tienes dos días:** Día 1 y Día 2. Son los que más afirmaciones convierten de
«escrito» a «ejecutado».

---

## 10. Qué me devuelves

Guarda todo en `docs/evidencia/ejecucion_plataforma/<bloque>/` y avísame. Para cada
tarea necesito:

1. **Qué ejecutaste** (comando o pasos).
2. **Qué salió** (salida, captura o plan de ejecución).
3. **Si coincidió con lo esperado**, y si no, el error exacto.
4. **Fecha y plataforma** (workspace, región, tipo de cómputo).

**Sin secretos:** nada de cadenas de conexión, tokens ni contraseñas. Si una captura los
muestra, tápalos.

Con eso yo actualizo `ESTADO_IMPLEMENTACION.md`, `PENDIENTES_ACTUALES.md`, el README, el
deck y el simulacro, y convierto cada «escrito, no ejecutado» en una afirmación
respaldada con fecha y artefacto.

---

## 11. Control de costo mientras pruebas

| Riesgo | Palanca |
|---|---|
| Capacidad Fabric encendida sin usarse | **Pausarla** al terminar cada sesión. Es la que más cuesta |
| Cómputo Databricks ocioso | Serverless no cobra en reposo; un clúster clásico sí. Usa auto-terminación |
| Azure SQL encendida | Apágala o usa Docker local |
| Job programado que olvidaste | Pausa el schedule al acabar las pruebas |
| No saber en qué se fue | Etiqueta todo desde el principio y revisa `system.billing.usage` |

**Regla práctica:** al cerrar cada día, revisa que no quede nada encendido. El costo de
estas pruebas debería ser de horas de cómputo, no de días.

---

## Resumen en una tabla

| Bloque | Tareas | Tiempo | Cierra | Prioridad |
|---|---|---|---|---|
| D · Databricks | D0–D8 | 8 h | E04, E04b, parte de E05 | Alta |
| F · Fabric | F0–F5 | 6 h | E04, F4 verifica la lámina 18 | Alta si es tu piloto |
| **P · Power BI** | P1–P4 | **3 h** | **E03** | **La más alta: barata y muy visible** |
| S · SQL Server | S0–S5 | 5 h | E01, E02 | Media |
| O · Operación | O1–O5 | 2 h | E05 parcial | Media |
| I · IA | I1–I2 | 2 h + | U05, E06 | Alta (U05 bloquea) |

**Si tuvieras que hacer una sola cosa:** el bloque P. Es tres horas y elimina la
afirmación más débil del proyecto.
