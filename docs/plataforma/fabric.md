# Microsoft Fabric · paso a paso

> Versión con más profundidad conceptual (OneLake, Direct Lake, por qué la prueba de
> transacción de FAB-08 importa, glosario y preguntas frecuentes):
> [fabric_detallada.md](fabric_detallada.md).

**Qué vas a lograr aquí:** ejecutar el mismo ETL en un Lakehouse de Fabric, correr los
doce escenarios, **verificar si Warehouse soporta transacción multi-tabla** —la prueba
que cambia un argumento de arquitectura— y dejar listo el modelo semántico para
Power BI. Cierra **E04** en Fabric y prepara **E03**.

**Tiempo total:** 6 h. **Prerrequisito:** una capacidad Fabric asignada.

> **Validar Fabric no acredita Databricks, ni al revés.** Si haces los dos, la evidencia
> va por separado y así se declara.

---

## FAB-01 · Confirmar capacidad y crear el workspace ⏱️ 15 min

**Por qué.** En Fabric todo cuelga de una **capacidad** y es lo que determina el costo.
Necesito saber cuál tienes para que la lámina de FinOps del deck tenga tu dato real y no
uno genérico.

**Pasos**

1. Entra a <https://app.fabric.microsoft.com>.
2. Arriba a la derecha → **Configuración ⚙️ → Configuración de administración → Capacidades**
   (o **Trial** si estás en prueba gratuita).
3. **Anota tres cosas:** el SKU (F2, F8, F64, Trial…), la región y si el botón
   **Pausar** está disponible.
4. **Crear workspace** → nómbralo `andina` → en **Avanzado**, asígnalo a esa capacidad.

**✅ Debe salir:** el workspace `andina` creado y mostrando la capacidad asignada.

**❌ Si no puedes asignar capacidad:** estás en un workspace «Mi área», que no sirve para
Lakehouse. Crea uno nuevo.

**📎 Evidencia:** `evidencia/fabric/01_capacidad.png` mostrando SKU y región.

> **Costo:** si tienes el botón **Pausar**, úsalo al terminar cada sesión. Una capacidad
> encendida cobra aunque nadie la use: es la palanca de costo más grande de Fabric.

---

## FAB-02 · Crear el Lakehouse ⏱️ 10 min

**Pasos**

1. Dentro del workspace `andina` → **+ Nuevo → Lakehouse**.
2. Nómbralo exactamente `andina`.
3. Espera a que aparezcan las dos secciones: **Tables** y **Files**.

**✅ Debe salir:** el Lakehouse `andina` con `Tables` y `Files` vacíos.

**📎 Evidencia:** `evidencia/fabric/02_lakehouse.png`.

---

## FAB-03 · Subir los CSV ⏱️ 15 min

**Por qué.** El notebook en modo Fabric lee de `Files/andina/raw`.

**Pasos**

1. En el Lakehouse → **Files** → clic derecho → **Nueva subcarpeta** → `andina`.
2. Dentro de `andina` → **Nueva subcarpeta** → `raw`.
3. Entra a `raw` → **Cargar → Cargar archivos** → selecciona los cuatro de
   `data/original/`: `clientes.csv`, `pagos.csv`, `pedidos.csv`, `tickets_soporte.csv`.

**✅ Debe salir:** la ruta `Files/andina/raw/` con los cuatro archivos.

**⚠️ Importante:** la ruta tiene que ser exactamente esa. El notebook usa
`RAW = "Files/andina/raw"`. Si la creas en otro sitio, cámbiala en la celda 2.

**📎 Evidencia:** `evidencia/fabric/03_archivos.png`.

---

## FAB-04 · Importar el notebook y adjuntar el Lakehouse ⏱️ 15 min

**Pasos**

1. En el workspace → **+ Nuevo → Importar notebook** → sube
   `fabric/notebooks/andina_etl_spark.ipynb`.
2. Ábrelo. Debe tener **13 celdas**.
3. 🔴 **Paso que más se olvida:** en el panel izquierdo del notebook, **Lakehouses → +
   Agregar** → elige `andina` y márcalo como **predeterminado**.
   Sin esto, `Files/andina/raw` no resuelve y la celda 6 falla.
4. Celda 2: confirma que dice `PLATAFORMA = "fabric"` (es el valor por defecto, no hay
   que cambiar nada).

**✅ Debe salir:** el notebook con el Lakehouse `andina` adjunto y marcado como
predeterminado.

**📎 Evidencia:** `evidencia/fabric/04_notebook.png` con el panel de Lakehouses visible.

---

## FAB-05 · Primera ejecución completa ⏱️ 45 min ⭐

**Pasos**

1. **Ejecutar todo**. La primera vez el pool de Spark tarda unos minutos en arrancar.
2. Revisa las salidas.

**✅ Debe salir** (los datos son los reales del caso, así que las cifras son exactas):

| Celda | Qué debe imprimir |
|---|---|
| 5 | Sin error: crea **19 tablas** Delta y 2 vistas |
| 6 | `clientes 6040`, `pedidos 19734`, `pagos 20883`, `tickets_soporte 2125`, extras `ninguna` |
| 8 | `clientes insertados=6040` · `pedidos insertados=19270 cuarentena_nueva=511` · `pagos insertados=20124 cuarentena_nueva=759` |
| 10 | `dias de venta recalculados: 636` |
| 11 | `estrella: {'gold_fact_pedido': 19270, 'gold_fact_pago': 20124, 'gold_fact_ticket': 2125, 'gold_fact_venta_neta_diaria': 7925}` |
| 12 | `publicado: {'estado': 'VALIDADO', 'venta_neta': 14177333600, ...}` |
| 13 | **Cinco líneas `OK`** |

**❌ Si falla**

| Error | Causa | Qué hacer |
|---|---|---|
| `Path does not exist: Files/andina/raw/...` | El Lakehouse no está adjunto | Repite FAB-04 paso 3 |
| `AnalysisException` en la celda 5 | Delta no disponible | Confirma que el Lakehouse es Lakehouse y no Warehouse |
| La celda 13 falla el `assert` | Cifras distintas | Mándame la salida: es un hallazgo de paridad real |

**📎 Evidencia:** exporta el notebook ejecutado →
`evidencia/fabric/05_primera_corrida.ipynb` + captura de la celda 13.

**Cierra:** **E04-01** en Fabric.

---

## FAB-06 · Comprobar las tablas en el Lakehouse ⏱️ 10 min

**Pasos**

1. Vuelve al Lakehouse → **Tables**. Refresca.
2. Deben aparecer las 19 tablas.
3. Usa el **SQL analytics endpoint** (arriba a la derecha, cambia de *Lakehouse* a
   *SQL analytics endpoint*) y ejecuta:

```sql
SELECT SUM(venta_neta) AS venta FROM gold_venta_neta_diaria;
-- 14177333600

SELECT COUNT(*) FROM gold_fact_pedido;
-- 19270

SELECT canal, SUM(venta_neta) FROM gold_venta_neta_diaria GROUP BY canal ORDER BY 2 DESC;
-- APP 6061702800 / WEB 4606783900 / TIENDA 3508846900
```

**✅ Debe salir:** esas cifras exactas.

**📎 Evidencia:** `evidencia/fabric/06_tablas.png` + `06_consultas.txt`.

---

## FAB-07 · Los doce escenarios ⏱️ 2–3 h

Son los mismos que en Databricks, con dos diferencias de sintaxis.

Usa la tabla de [databricks.md → DBX-08](databricks.md#dbx-08--los-doce-escenarios),
cambiando:

- Las rutas: `Files/andina/raw/...` en vez de `/Volumes/...`.
- Los nombres de tabla: en Fabric son de una parte (`silver_pedidos`), no de tres.
- Para volver a subir un CSV modificado, usa la UI (**Cargar → sobrescribir**), no el
  CLI de Databricks.
- `DESCRIBE HISTORY silver_pedidos` y `RESTORE TABLE silver_pedidos TO VERSION AS OF N`
  funcionan igual: son comandos de Delta, no de la plataforma.

**El escenario E04-08 sigue siendo el más importante:** para el notebook después de la
celda 11 y comprueba que `publicacion_actual` no se movió y que `v_fact_pedido` sigue
mostrando el run anterior.

**📎 Evidencia:** `evidencia/fabric/07_e04-*`.

---

## FAB-08 · La prueba que solo Fabric permite ⏱️ 45 min ⭐⭐

**Por qué importa.** Todo el diseño de publicación del proyecto —escribir los hechos con
`run_id` y mover un puntero— existe **porque Delta no tiene transacción entre tablas**.
Pero **Fabric Warehouse sí soporta transacciones multi-tabla en T-SQL**. Si se confirma,
en ese destino el patrón sobraría y se podría usar una transacción real, como en DuckDB.

Esto convierte la lámina 18 del deck de hipótesis en argumento verificado, y te da la
mejor respuesta a *«¿por qué Fabric y no Databricks?»*.

**Pasos**

1. En el workspace → **+ Nuevo → Warehouse** → nómbralo `andina_wh`.
2. Abre el editor SQL y crea dos tablas de prueba:

```sql
CREATE TABLE dbo.t_a (id INT, valor INT);
CREATE TABLE dbo.t_b (id INT, valor INT);
```

3. **La prueba del rollback:**

```sql
BEGIN TRANSACTION;
  INSERT INTO dbo.t_a VALUES (1, 100);
  INSERT INTO dbo.t_b VALUES (1, 200);
ROLLBACK;

SELECT 't_a' AS tabla, COUNT(*) AS filas FROM dbo.t_a
UNION ALL
SELECT 't_b', COUNT(*) FROM dbo.t_b;
```

**✅ Hipótesis confirmada si:** las dos tablas quedan en **0 filas**. El rollback
deshizo ambas inserciones → hay transacción multi-tabla.

**❌ Hipótesis refutada si:** alguna tabla conserva su fila, o el `BEGIN TRANSACTION`
da error.

4. **La prueba del commit**, para descartar que simplemente no insertara nada:

```sql
BEGIN TRANSACTION;
  INSERT INTO dbo.t_a VALUES (2, 100);
  INSERT INTO dbo.t_b VALUES (2, 200);
COMMIT;

SELECT 't_a' AS tabla, COUNT(*) AS filas FROM dbo.t_a
UNION ALL
SELECT 't_b', COUNT(*) FROM dbo.t_b;
-- Ambas deben tener 1 fila
```

5. **Prueba adicional:** intenta el DDL del proyecto en Warehouse:

```sql
-- Ejecuta sqlserver/ddl_tsql.sql por partes y anota qué NO soporta Warehouse.
-- Candidatos habituales: índices no agrupados, algunas restricciones, IDENTITY.
```

**📎 Evidencia:** `evidencia/fabric/08_transaccion.txt` con los cuatro resultados y
`08_ddl_warehouse.txt` con la lista de lo que no soportó.

**Esto es oro para la sustentación.** Avísame del resultado y actualizo el deck y el
documento de traslado a Delta.

---

## FAB-09 · Modelo semántico Direct Lake ⏱️ 30 min

**Por qué.** Es lo que permite que Power BI lea las tablas Delta **sin importar datos**,
y es el puente al bloque de Power BI.

**Pasos**

1. En el Lakehouse → arriba a la derecha → **Nuevo modelo semántico**.
2. Nómbralo `andina_modelo`.
3. Selecciona exactamente estas tablas:
   `gold_fact_pedido`, `gold_fact_venta_neta_diaria`, `gold_dim_fecha`,
   `gold_dim_canal`, `gold_dim_categoria`, `gold_dim_cliente`.
4. Abre el modelo y crea las relaciones arrastrando campo sobre campo:

| Desde | Hacia | Cardinalidad | Dirección |
|---|---|---|---|
| `gold_fact_pedido[fecha_key]` | `gold_dim_fecha[fecha_key]` | Varios a uno | Simple |
| `gold_fact_pedido[canal_key]` | `gold_dim_canal[canal_key]` | Varios a uno | Simple |
| `gold_fact_pedido[categoria_key]` | `gold_dim_categoria[categoria_key]` | Varios a uno | Simple |
| `gold_fact_pedido[cliente_key]` | `gold_dim_cliente[cliente_key]` | Varios a uno | Simple |

**✅ Debe salir:** el diagrama con las cuatro relaciones y `gold_dim_fecha` en el centro.

**📎 Evidencia:** `evidencia/fabric/09_modelo.png` con el diagrama de relaciones.

**Sigue en:** [powerbi.md](powerbi.md), que usa este modelo.

---

## FAB-10 · Programar el notebook ⏱️ 20 min *(opcional)*

1. En el workspace → el notebook → **⋯ → Programar**.
2. Frecuencia diaria, 5:00 a. m., zona `(UTC-05:00) Bogotá`.
3. **Déjalo deshabilitado** hasta que decidas operarlo de verdad.

**📎 Evidencia:** `evidencia/fabric/10_schedule.png`.

---

## FAB-11 · Pausar la capacidad ⏱️ 5 min 💰

**No te saltes esto.** Al terminar la sesión:

1. **Configuración ⚙️ → Capacidades** → tu capacidad → **Pausar**.
2. Confirma que el estado queda en *Paused*.

Una capacidad encendida el fin de semana cuesta igual que una en uso.

**📎 Evidencia:** `evidencia/fabric/11_pausa.png`.

---

## Lista de cierre

| Tarea | Hecho | Evidencia | Cierra |
|---|---|---|---|
| FAB-01 Capacidad y workspace | ☐ | `01_capacidad.png` | dato de costo real |
| FAB-02 Lakehouse | ☐ | `02_lakehouse.png` | — |
| FAB-03 CSV | ☐ | `03_archivos.png` | — |
| FAB-04 Notebook adjunto | ☐ | `04_notebook.png` | — |
| FAB-05 Primera corrida | ☐ | `05_primera_corrida.ipynb` | **E04-01** |
| FAB-06 Tablas y consultas | ☐ | `06_consultas.txt` | — |
| FAB-07 Doce escenarios | ☐ | `07_e04-*` | **E04** |
| FAB-08 Transacción multi-tabla | ☐ | `08_transaccion.txt` | **lámina 18 verificada** |
| FAB-09 Modelo semántico | ☐ | `09_modelo.png` | desbloquea **E03** |
| FAB-10 Schedule | ☐ | `10_schedule.png` | parte de E05 |
| FAB-11 Pausa | ☐ | `11_pausa.png` | control de costo |
