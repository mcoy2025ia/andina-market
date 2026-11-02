# Databricks · paso a paso

> Versión con más profundidad conceptual (por qué funciona así cada mecanismo, más
> casos de error, glosario y preguntas frecuentes): [databricks_detallada.md](databricks_detallada.md).

**Qué vas a lograr aquí:** ejecutar el ETL completo en Databricks con Delta, correr los
doce escenarios de validación y dejarlo desplegado como job. Eso cierra **E04**, el
bloqueador **E04b** y parte de **E05**.

**Tiempo total:** 8 h repartibles. **Prerrequisito:** ninguno; este bloque arranca de cero.

Los datos del caso son ficticios, así que se cargan los CSV reales de `data/original/`
y **las cifras de referencia aplican**: al final la celda 13 debe imprimir `OK` en las
cinco líneas.

> **Regla.** Si un paso no da lo que dice **✅ Debe salir**, no sigas: anota el error
> exacto en la evidencia y avísame. Un «casi» aquí se convierte en una afirmación falsa
> en la sustentación.

**Convención:** todos los comandos llevan `--profile finanzauto`. Si usas otro nombre,
cámbialo en todos.

---

## DBX-01 · Arreglar el perfil del CLI ⏱️ 10 min 🔴

**Por qué.** Tu único perfil en `.databrickscfg` tiene como **nombre** una URL de
notebook pegada y marca `Valid: NO`. Hasta arreglarlo, ningún comando funciona.

**Pasos**

1. Mira lo que hay ahora:

```bash
databricks auth profiles
```

2. Crea un perfil limpio. Se abre el navegador y te pide aprobar:

```bash
databricks auth login --host https://dbc-ebd35512-279a.cloud.databricks.com --profile finanzauto
```

3. Comprueba:

```bash
databricks auth profiles
databricks current-user me --profile finanzauto
```

**✅ Debe salir:** `finanzauto` con `Valid: YES`, y tu correo en `current-user me`.

**❌ Si falla**
- *«cannot configure default credentials»* → falta `--profile` en el comando.
- Sigue apareciendo el perfil viejo con la URL larga → abre `~/.databrickscfg` en un
  editor y borra **solo** esa sección `[https://dbc-...]`. No borres el archivo.

**📎 Evidencia:** `evidencia/databricks/01_perfil.txt` con la salida de
`databricks auth profiles`. No incluye tokens.

---

## DBX-02 · Crear catálogo, esquema y volumen ⏱️ 10 min

**Por qué.** El notebook usa nombres de tres partes `andina.datos.<tabla>` y lee los CSV
de un volumen de Unity Catalog.

**Pasos**

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

Verifica:

```bash
databricks catalogs list --profile finanzauto
databricks schemas list andina --profile finanzauto
databricks volumes list andina.datos --profile finanzauto
```

**✅ Debe salir:** el catálogo `andina`, el esquema `datos` y el volumen
`andina.datos.raw`.

**❌ Si falla con `PERMISSION_DENIED`:** no eres administrador del metastore. Dos
salidas: pide el permiso `CREATE CATALOG`, o usa un catálogo existente y en **DBX-05**
cambia la función `T()` de la celda 2 para que apunte a él.

**📎 Evidencia:** `evidencia/databricks/02_catalogo.txt`.

---

## DBX-03 · Comprobar si hay serverless ⏱️ 5 min

**Por qué.** Serverless es el cómputo predeterminado para jobs y pipelines, y cambia la
recomendación de costo. Si no lo tienes, todo corre igual en clásico.

**Pasos**

1. En la UI, menú lateral → **Compute**.
2. Mira si existe la pestaña **Serverless** o si al crear un notebook te ofrece
   «Serverless» como cómputo.
3. Anota el resultado: sí o no.

**📎 Evidencia:** `evidencia/databricks/03_serverless.png`.

> Si **no** hay serverless, salta **DBX-08** y anótalo: la lámina de costo del deck se
> ajusta con ese dato.

---

## DBX-04 · Subir los CSV ⏱️ 10 min

**Pasos**

```bash
databricks fs cp -r --overwrite data/original dbfs:/Volumes/andina/datos/raw --profile finanzauto

databricks fs ls dbfs:/Volumes/andina/datos/raw --profile finanzauto
```

**⚠️ El prefijo `dbfs:` es obligatorio** aunque sea un volumen de Unity Catalog. Sin él,
el CLI lo trata como ruta local y falla con *«no such directory»*.

**✅ Debe salir:** los cuatro archivos — `clientes.csv`, `pagos.csv`, `pedidos.csv`,
`tickets_soporte.csv`.

**📎 Evidencia:** `evidencia/databricks/04_archivos.txt`.

---

## DBX-05 · Importar el notebook ⏱️ 10 min

**Pasos**

1. Importa (cambia `TU_USUARIO` por tu correo):

```bash
databricks workspace import /Users/TU_USUARIO/andina_etl_spark \
  --file fabric/notebooks/andina_etl_spark.ipynb \
  --format JUPYTER --profile finanzauto
```

2. Ábrelo en la UI. Debe tener **13 celdas**: 1 de texto y 12 de código.
3. **Celda 2** (`=== 1. Configuración`): cambia la primera línea de configuración:

```python
PLATAFORMA = "databricks"      # venía como "fabric"
```

4. Confirma en esa misma celda que las rutas quedan:

```python
RAW, BRONZE = "/Volumes/andina/datos/raw", "/Volumes/andina/datos/bronze"
```

**✅ Debe salir:** el notebook abierto, 13 celdas, `PLATAFORMA = "databricks"`.

**❌ Si falla el import:** `databricks workspace import --help` para ver los formatos
soportados en tu versión; alternativa, súbelo desde la UI con **Workspace → Import**.

**📎 Evidencia:** `evidencia/databricks/05_notebook.png` con la celda 2 visible.

---

## DBX-06 · Primera ejecución completa ⏱️ 40 min ⭐

**Por qué.** Es la tarea que convierte «escrito» en «ejecutado». Cierra **E04-01**.

**Pasos**

1. Adjunta un cómputo (serverless si existe, si no un clúster pequeño).
2. **Run all**. Deja que termine.
3. Revisa las salidas en este orden:

**✅ Debe salir, celda por celda**

| Celda | Qué hace | Qué debe imprimir |
|---|---|---|
| 5 | Crea las tablas Delta | Sin error. Crea **19 tablas** y 2 vistas |
| 6 | Contrato de los CSV | 4 líneas: `clientes 6040`, `pedidos 19734`, `pagos 20883`, `tickets_soporte 2125`, columnas extra `ninguna` |
| 8 | Clientes, pedidos, pagos | `clientes insertados=6040`, `pedidos insertados=19270 cuarentena_nueva=511`, `pagos insertados=20124 cuarentena_nueva=759` |
| 10 | Venta neta diaria | `dias de venta recalculados: 636` |
| 11 | Modelo estrella | `estrella: {'gold_fact_pedido': 19270, 'gold_fact_pago': 20124, 'gold_fact_ticket': 2125, 'gold_fact_venta_neta_diaria': 7925}` |
| 12 | Publicación | `publicado: {'estado': 'VALIDADO', 'pedidos': 19270, 'venta_neta': 14177333600, ...}` |
| 13 | Verificación | **Cinco líneas con `OK`** y la tabla de cuarentena por regla |

**❌ Si falla**

| Error | Causa | Qué hacer |
|---|---|---|
| `AnalysisException ... cache` | Serverless no admite `.cache()` | Es **DBX-07**. Corre primero en clásico |
| `PATH_NOT_FOUND` en `/Volumes/...` | El volumen no existe o el nombre no coincide | Repite DBX-02 y DBX-04 |
| `TABLE_OR_VIEW_NOT_FOUND` | El catálogo de `T()` no coincide | Revisa la celda 2 |
| La celda 13 falla el `assert` | Las cifras no coinciden | Mándame la salida completa: es un hallazgo de paridad real |

**📎 Evidencia:** exporta el notebook ejecutado con salidas →
`evidencia/databricks/06_primera_corrida.ipynb`. Y captura de la celda 13.

**Cierra:** **E04-01**.

---

## DBX-07 · Quitar el bloqueador de serverless ⏱️ 30 min 🔴

**Solo si DBX-06 falló en serverless por `.cache()`, o si quieres cerrar E04b.**

**Por qué.** El notebook usa `.cache()` en cuatro puntos y Databricks serverless no lo
admite. Y quitarlo sin más no basta: en la celda 8 ese `.cache()` además **materializa**
antes del `MERGE`, cuyo origen lee la misma tabla que escribe (`silver_pedidos`, vía
`hash_negocio`). La corrección correcta es una tabla de staging.

**Pasos**

1. En tu máquina, abre `src/shared/spark/build_notebook.py`.
2. Busca las tres apariciones dentro de la constante `PIPELINE`:

```python
ped_ok = ped_ok.cache()
pag_raw = pag_raw.cache()
pag_ok = pag_ok.cache()
```

3. Sustituye cada una por una materialización explícita:

```python
# ped_ok = ped_ok.cache()
ped_ok.write.mode("overwrite").saveAsTable(T("stg_pedidos"))
ped_ok = spark.table(T("stg_pedidos"))
```

(lo mismo para `pag_raw` → `stg_pagos_raw` y `pag_ok` → `stg_pagos`)

4. La cuarta está en `src/shared/spark/extensiones_spark.py`, en `verificar_contrato`:
   quita `.cache()` y deja que cuente dos veces, o materializa igual.
5. Regenera y vuelve a importar:

```bash
python src/shared/spark/build_notebook.py
python -m pytest tests/ -q          # las pruebas locales deben seguir en verde
databricks workspace import /Users/TU_USUARIO/andina_etl_spark \
  --file fabric/notebooks/andina_etl_spark.ipynb \
  --format JUPYTER --overwrite --profile finanzauto
```

6. Vuelve a ejecutar todo en **serverless**.

**✅ Debe salir:** el notebook completa en serverless, con las mismas cifras de DBX-06.

**📎 Evidencia:** `evidencia/databricks/07_serverless.txt` con el error antes y la
corrida correcta después.

**Avísame del resultado.** Si funciona, lo incorporo al generador con sus pruebas y
cierro E04b en la documentación.

---

## DBX-08 · Los doce escenarios ⏱️ 2–3 h

Esta es la parte que de verdad valida el diseño. Cada escenario provoca un fallo a
propósito y comprueba que el sistema responde como se diseñó.

### E04-02 · Segunda carga sin cambios ⏱️ 10 min
**Haz:** vuelve a ejecutar todas las celdas sin tocar nada.
**✅ Debe salir:** `insertados=0 actualizados=0` en las tres tablas, y
`bronze=ya existia`.
**📎** `08_e04-02_segunda_carga.png`

### E04-03 · Archivo modificado ⏱️ 15 min
**Haz:** edita `data/original/pedidos.csv`, cambia el `valor_bruto` de un pedido
ENTREGADO, vuelve a subir con `databricks fs cp -r --overwrite ...` y reejecuta.
**✅ Debe salir:** `actualizados=1` (no 19.270), y la venta del día de ese pedido cambia.
**📎** `08_e04-03_modificado.png` + `DESCRIBE HISTORY andina.datos.silver_pedidos LIMIT 3`

### E04-04 · Cabecera alterada ⏱️ 10 min
**Haz:** renombra la columna `canal` a `canal_venta` en `pedidos.csv`, sube y reejecuta.
**✅ Debe salir:** falla en la **celda 6** con `ErrorContrato: pedidos: faltan columnas
['canal']`, **antes** de tocar Bronze. Comprueba que no hay versión nueva de
`bronze_manifest`.
**📎** `08_e04-04_contrato.png`
**Deshaz el cambio** antes de seguir.

### E04-05 · Pago tardío fuera de ventana ⏱️ 20 min
**Haz:** añade a `pagos.csv` un pago con un `id_pedido` que esté en cuarentena, con
`fecha_carga` muy antigua. Sube y reejecuta.
**✅ Debe salir:** el pago se relee aunque esté fuera del watermark. Compruébalo:

```sql
SELECT * FROM andina.datos.cuarentena
WHERE regla_violada IN ('PAGO_HUERFANO','PEDIDO_EN_CUARENTENA') LIMIT 10;
```

**📎** `08_e04-05_pago_tardio.txt`

### E04-06 · Pedido que pasa a inválido ⏱️ 15 min
**Haz:** cambia el `valor_bruto` de un pedido ya cargado a `-1000`. Sube y reejecuta.
**✅ Debe salir:** el pedido **sale** de Silver (`retirados=1`), aparece en cuarentena con
`VALOR_BRUTO_NO_POSITIVO`, y la venta de su día **baja**.
**📎** `08_e04-06_retirado.txt` con la venta del día antes y después.

### E04-07 · Incidencia que se resuelve ⏱️ 10 min
**Haz:** corrige el valor del escenario anterior y reejecuta.
**✅ Debe salir:**

```sql
SELECT estado, motivo FROM andina.datos.calidad_incidencias
WHERE id_registro = '<el_id_del_pedido>';
-- RESUELTA, 'No incumple en la última reevaluación'
SELECT count(*) FROM andina.datos.cuarentena WHERE id_registro = '<el_id>';
-- > 0 : la historia NO se borra
```

**📎** `08_e04-07_incidencia.txt`

### E04-08 · Fallo entre tablas ⏱️ 20 min ⭐ *la más importante*
**Haz:** ejecuta las celdas 1 a 11 y **para ahí** (no ejecutes la 12). Luego consulta:

```sql
SELECT * FROM andina.datos.publicacion_actual;
SELECT count(*) FROM andina.datos.v_fact_pedido;
SELECT count(*) FROM andina.datos.gold_fact_pedido;
```

**✅ Debe salir:** `gold_fact_pedido` tiene filas del run nuevo, pero
`publicacion_actual` sigue apuntando al run **anterior** y `v_fact_pedido` muestra el
conteo anterior, no el nuevo. Eso es exactamente lo que sustituye a la transacción.
**📎** `08_e04-08_publicacion.txt` — **esta es la evidencia estrella del bloque.**

### E04-09 · Compuerta disparada ⏱️ 15 min
**Haz:** en la celda 12 cambia:

```python
POLITICA = PoliticaPublicacion(min_pedidos=999999)
```

y ejecútala.
**✅ Debe salir:** `PUBLICACIÓN BLOQUEADA: Volumen menor que mínimo configurado` y la
celda falla. `publicacion_actual` no se mueve.
**📎** `08_e04-09_compuerta.png`. Devuelve `POLITICA = PoliticaPublicacion()` después.

### E04-10 · Recuperación ⏱️ 20 min
**Haz:**

```sql
DESCRIBE HISTORY andina.datos.silver_pedidos;
-- elige una versión anterior, por ejemplo 2
RESTORE TABLE andina.datos.silver_pedidos TO VERSION AS OF 2;
SELECT count(*) FROM andina.datos.silver_pedidos;
```

Luego reejecuta el notebook completo.
**✅ Debe salir:** la tabla vuelve al conteo de esa versión, y tras reejecutar todo
vuelve a cuadrar en 19.270 con la misma venta neta.
**📎** `08_e04-10_restore.txt`

### E04-11 · Claves estables ⏱️ 10 min
**Haz:**

```sql
SELECT * FROM andina.datos.gold_dim_canal ORDER BY canal_key;
```

Anótalo, reejecuta el notebook y vuelve a consultarlo.
**✅ Debe salir:** exactamente las mismas claves. Si cambiaran, cualquier informe
guardado apuntaría a otro canal.
**📎** `08_e04-11_claves.txt` con el antes y el después.

### E04-12 · Paridad final ⏱️ 10 min
**Haz:** celda 13 completa.
**✅ Debe salir:** `OK` en las cinco líneas y venta neta `14.177.333.600`.
**📎** `08_e04-12_paridad.png`

**Cierra:** **E04 completo en Databricks.**

---

## DBX-09 · Desplegarlo como job con bundle ⏱️ 45 min

**Por qué.** Demuestra despliegue reproducible y cierra parte de **E05**.

**Pasos**

1. Inicializa el bundle (elige la plantilla `default-python`):

```bash
databricks bundle init --profile finanzauto
```

2. Edita el YAML del job. **Lo importante:**

```yaml
resources:
  jobs:
    andina_etl:
      name: andina_etl
      # Sin job_clusters, new_cluster ni node_type_id: así corre en SERVERLESS,
      # que es el cómputo predeterminado.
      performance_target: STANDARD   # lote nocturno sin compromiso de latencia
      tags:
        proyecto: andina
        responsable: datos
      tasks:
        - task_key: etl
          notebook_task:
            notebook_path: /Users/TU_USUARIO/andina_etl_spark
      schedule:
        quartz_cron_expression: "0 0 5 * * ?"   # 5:00 a. m.
        timezone_id: America/Bogota
        pause_status: PAUSED                     # arranca pausado
```

3. Valida y despliega:

```bash
databricks bundle validate --strict --target dev --profile finanzauto
databricks bundle deploy --target dev --profile finanzauto
databricks bundle run andina_etl --target dev --profile finanzauto
```

**✅ Debe salir:** `validate` sin errores, `deploy` correcto y la ejecución termina bien.

**Por qué `STANDARD` y no `PERFORMANCE_OPTIMIZED`:** este ETL es un lote nocturno sin
nadie esperando el resultado. `STANDARD` arranca en minutos y **cuesta menos**;
`PERFORMANCE_OPTIMIZED` se reserva para lo que tiene un plazo real.

**Por qué etiquetar:** sin etiquetas no se puede repartir el costo por área después, y
la conversación de FinOps se vuelve una opinión.

**📎 Evidencia:** `evidencia/databricks/09_bundle.txt` con las tres salidas.

---

## DBX-10 · Gobierno: permisos y enmascaramiento ⏱️ 30 min

**Pasos**. En un notebook o en el editor SQL:

```sql
-- 1. Permisos en el securable más estrecho que funcione
GRANT USE CATALOG ON CATALOG andina TO `<tu_grupo>`;
GRANT USE SCHEMA  ON SCHEMA  andina.datos TO `<tu_grupo>`;
GRANT SELECT      ON TABLE   andina.datos.gold_fact_venta_neta_diaria TO `<tu_grupo>`;

-- 2. Comprobar quién puede qué
SHOW GRANTS ON TABLE andina.datos.gold_fact_venta_neta_diaria;

-- 3. Enmascarar el documento (aunque los datos sean ficticios, demuestra el mecanismo)
CREATE OR REPLACE FUNCTION andina.datos.mask_doc(doc STRING)
RETURN CASE WHEN is_account_group_member('auditores') THEN doc
            ELSE 'XXXX' || right(doc, 3) END;

ALTER TABLE andina.datos.silver_clientes
  ALTER COLUMN documento_limpio SET MASK andina.datos.mask_doc;

SELECT documento_limpio FROM andina.datos.silver_clientes LIMIT 5;
```

**✅ Debe salir:** `SHOW GRANTS` lista los permisos, y el `SELECT` devuelve el documento
enmascarado si no estás en el grupo `auditores`.

**📎 Evidencia:** `evidencia/databricks/10_gobierno.txt`.

---

## DBX-11 · Linaje y costo ⏱️ 20 min

```sql
-- Linaje: de dónde sale cada tabla Gold
SELECT source_table_full_name, target_table_full_name
FROM system.access.table_lineage
WHERE target_table_full_name LIKE 'andina.datos.gold%'
  AND event_date >= current_date() - 7;

-- Quién consultó qué
SELECT event_time, user_identity.email, action_name
FROM system.access.audit
WHERE event_date >= current_date() - 7
ORDER BY event_time DESC LIMIT 20;

-- Consumo: ejecútalo unos días después de DBX-09
SELECT usage_date, sku_name, SUM(usage_quantity) AS dbus
FROM system.billing.usage
WHERE usage_date >= current_date() - 30
GROUP BY usage_date, sku_name
ORDER BY usage_date DESC;
```

**❌ Si falla con permisos:** necesitas acceso a las tablas de sistema:

```sql
GRANT USE CATALOG ON CATALOG system TO `<tu_usuario>`;
GRANT SELECT ON SCHEMA system.access TO `<tu_usuario>`;
GRANT SELECT ON SCHEMA system.billing TO `<tu_usuario>`;
```

**📎 Evidencia:** `evidencia/databricks/11_linaje_costo.txt`.

---

## DBX-12 · Apagar todo ⏱️ 5 min

1. Pausa el schedule del job si no lo vas a usar.
2. Termina los clústeres clásicos (serverless no cobra en reposo).
3. Comprueba en **Compute** que no queda nada corriendo.

**📎 Evidencia:** `evidencia/databricks/12_apagado.png`.

---

## Lista de cierre

| Tarea | Hecho | Evidencia | Cierra |
|---|---|---|---|
| DBX-01 Perfil | ☐ | `01_perfil.txt` | — |
| DBX-02 Catálogo | ☐ | `02_catalogo.txt` | — |
| DBX-03 Serverless | ☐ | `03_serverless.png` | dato de costo |
| DBX-04 CSV | ☐ | `04_archivos.txt` | — |
| DBX-05 Notebook | ☐ | `05_notebook.png` | — |
| DBX-06 Primera corrida | ☐ | `06_primera_corrida.ipynb` | **E04-01** |
| DBX-07 Serverless | ☐ | `07_serverless.txt` | **E04b** |
| DBX-08 Doce escenarios | ☐ | `08_e04-*` | **E04** |
| DBX-09 Bundle | ☐ | `09_bundle.txt` | parte de **E05** |
| DBX-10 Gobierno | ☐ | `10_gobierno.txt` | lámina 19 |
| DBX-11 Linaje y costo | ☐ | `11_linaje_costo.txt` | lámina 22 |
| DBX-12 Apagado | ☐ | `12_apagado.png` | — |
