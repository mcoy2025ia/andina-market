# SQL Server · paso a paso

> Versión con más profundidad conceptual (qué es un plan de ejecución, por qué el
> `CAST` fuerza un *scan*, `IDENTITY_INSERT`, glosario y preguntas frecuentes):
> [sqlserver_detallada.md](sqlserver_detallada.md).

**Qué vas a lograr aquí:** ejecutar por primera vez el DDL y el T-SQL del proyecto en un
motor SQL Server real, cargar el modelo estrella y **medir la optimización con planes de
ejecución**. Cierra **E01** y **E02**.

**Tiempo total:** 5 h. **Prerrequisito:** el almacén local construido
(`python scripts/cargar_datos.py --desde-cero`).

> **Lo que aquí se juega.** Hoy el proyecto dice que el T-SQL y el DDL **nunca se han
> ejecutado**, y que la optimización se midió en SQLite, no en SQL Server. Son dos de
> las cuatro afirmaciones pendientes. Encontrar errores en este bloque **es el
> objetivo**, no un fracaso: el DDL se escribió sin motor donde probarlo.

---

## SQL-01 · Levantar SQL Server ⏱️ 20 min

Fabric Warehouse **no sirve** para este bloque: no es SQL Server y la medición de
optimización no sería comparable. Usa Docker local, que es gratis y es el motor real.

**Pasos**

1. Con Docker Desktop corriendo:

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=TuClave.Fuerte.2026" \
  -p 1433:1433 --name sqlserver-andina \
  -d mcr.microsoft.com/mssql/server:2022-latest
```

2. Comprueba que arrancó:

```bash
docker ps
docker logs sqlserver-andina --tail 20
```

3. Conéctate con Azure Data Studio, SSMS o `sqlcmd`:
   **Servidor:** `localhost,1433` · **Usuario:** `sa` · **Contraseña:** la de arriba ·
   **Confiar en el certificado del servidor:** sí.

4. Crea la base:

```sql
CREATE DATABASE andina;
GO
USE andina;
GO
```

**✅ Debe salir:** `docker ps` muestra el contenedor `Up`, y la base `andina` creada.

**❌ Si falla**
- *«port is already allocated»* → cambia a `-p 1434:1433` y conéctate a `localhost,1434`.
- El contenedor se reinicia en bucle → la contraseña no cumple la política: mínimo 8
  caracteres con mayúsculas, minúsculas, números y símbolos.

**⚠️ No pongas esa contraseña en ningún archivo del repositorio.**

**📎 Evidencia:** `evidencia/sqlserver/01_docker.txt` con la salida de `docker ps`.

---

## SQL-02 · Ejecutar el DDL ⏱️ 30 min ⭐

**Por qué.** `sqlserver/ddl_tsql.sql` crea 3 esquemas, las tablas Silver, las de control,
el modelo estrella Gold, las vistas y los índices. **Nunca se ha ejecutado.**

**Pasos**

1. Abre `sqlserver/ddl_tsql.sql`.
2. Ejecútalo completo contra la base `andina`.
3. Si falla, **no lo arregles en silencio**: anota el error exacto, la línea y qué
   objeto lo causó. Luego sáltalo y sigue, para encontrar todos los errores de una
   pasada en vez de uno por ejecución.

4. Verifica lo creado:

```sql
SELECT s.name AS esquema, t.name AS tabla
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
ORDER BY s.name, t.name;

SELECT name FROM sys.views ORDER BY name;

SELECT i.name AS indice, OBJECT_NAME(i.object_id) AS tabla
FROM sys.indexes i WHERE i.name IS NOT NULL ORDER BY 2, 1;
```

**✅ Debe salir:** los tres esquemas `silver`, `control` y `gold`; las tablas
`silver.clientes`, `silver.pedidos`, `silver.pagos`, `silver.tickets`;
`control.cuarentena`, `control.etl_run_log`, `control.etl_watermark`, `control.map_canal`;
las tablas `gold.dim_*` y `gold.fact_*`; la vista `silver.v_cliente_maestro`; y los
índices `ix_*`.

**📎 Evidencia:** `evidencia/sqlserver/02_ddl.txt` con la salida del script **y la lista
de errores si los hubo**. Esa lista me sirve: es el resultado de la tarea.

**Cierra:** la mitad de **E01**.

---

## SQL-03 · Cargar el modelo estrella ⏱️ 40 min

**Pasos**

1. Instala el conector:

```bash
pip install pyodbc
```

Necesitas también el **ODBC Driver 18 for SQL Server** instalado en el sistema.

2. Define la cadena de conexión **solo en la sesión**, nunca en un archivo:

```bash
# PowerShell
$env:DWH_CONNECTION_STRING = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=andina;UID=sa;PWD=TuClave.Fuerte.2026;TrustServerCertificate=yes"

# bash
export DWH_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=andina;UID=sa;PWD=TuClave.Fuerte.2026;TrustServerCertificate=yes"
```

3. **Primero el plan**, que no escribe nada:

```bash
python scripts/cargar_modelo_sqlserver.py --db data/warehouse.duckdb
```

**✅ Debe salir:** `{"modo": "plan_sin_conexion", "filas": {"dim_fecha": ..., "fact_pedido": 19270, "fact_pago": 20124, "fact_ticket": 2125, "fact_venta_neta_diaria": 7925}}`

4. **Ahora la carga.** Exige confirmar explícitamente que es un entorno de pruebas:

```bash
python scripts/cargar_modelo_sqlserver.py --db data/warehouse.duckdb --aplicar --entorno-pruebas
```

5. Verifica en SQL Server:

```sql
SELECT 'fact_pedido' t, COUNT(*) n FROM gold.fact_pedido
UNION ALL SELECT 'fact_pago', COUNT(*) FROM gold.fact_pago
UNION ALL SELECT 'fact_ticket', COUNT(*) FROM gold.fact_ticket
UNION ALL SELECT 'fact_venta_neta_diaria', COUNT(*) FROM gold.fact_venta_neta_diaria;
-- 19270 / 20124 / 2125 / 7925

SELECT SUM(venta_neta) FROM gold.fact_venta_neta_diaria;
-- 14177333600
```

6. 🔴 **Comprobación que no se puede saltar: los tipos monetarios.**

```sql
SELECT c.name AS columna, ty.name AS tipo, c.precision, c.scale
FROM sys.columns c
JOIN sys.types ty ON ty.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID('gold.fact_pedido')
  AND c.name IN ('valor_bruto','descuento','venta_neta');
```

**✅ Debe salir:** `bigint` en las tres. Si llegó como `decimal` o `float`, hay pérdida
de precisión y es un hallazgo importante: el proyecto se apoya en pesos enteros exactos.

**❌ Si falla con `IDENTITY_INSERT`:** las dimensiones `dim_canal`, `dim_categoria` y
`dim_cliente` llevan claves del modelo local que hay que preservar. El script ya lo
gestiona; si el error persiste, mándamelo.

**📎 Evidencia:** `evidencia/sqlserver/03_carga.txt` con los conteos, la suma y los tipos.

**Cierra:** **E01**.

---

## SQL-04 · Ejecutar venta y recompra ⏱️ 40 min

**Pasos**

1. Ejecuta `sqlserver/01_ventas_recompra.sql` contra `andina`.
2. Exporta los resultados de las dos consultas (venta mensual y recompra por cohorte).
3. Saca el equivalente local para comparar:

```bash
python -c "import duckdb,sys; con=duckdb.connect('data/warehouse.duckdb',read_only=True); q=open('duckdb/01_ventas_recompra.sql',encoding='utf-8').read().split(';')[0]; [print(r) for r in con.execute(q).fetchall()]" > evidencia/sqlserver/04_duckdb.txt
```

4. **Compara fila a fila.** No basta con que el total cuadre.

**✅ Debe salir:** mismas filas y mismos valores. Puntos donde mirar con lupa:

| Qué revisar | Esperado |
|---|---|
| **Meses sin ventas** | Aparecen con **cero**, no faltan. El calendario cubre los 21 meses × canal |
| Primer mes de la serie | Variación **nula**, no 0 % ni infinito |
| Total general | **14.177.333.600** |
| Reparto por canal | APP 42,8 % · WEB 32,5 % · TIENDA 24,7 % |
| Recompra 3 meses | 63,2 % cohortes 2025 → 49,2 % cohortes 2026 |
| Recompra 1 mes | 32,1 % → 26,1 % |

**❌ Si una fila no coincide:** es un hallazgo real de paridad entre dialectos. Mándamela
con las dos versiones; el T-SQL es un texto paralelo revisado línea a línea, no una
traducción automática, así que es justo donde pueden aparecer diferencias.

**📎 Evidencia:** `evidencia/sqlserver/04_tsql.txt`, `04_duckdb.txt` y `04_diferencias.txt`.

**Cierra:** la mitad de **E02**.

---

## SQL-05 · Generar volumen para la prueba de optimización ⏱️ 30 min

**Por qué.** Con 19.270 pedidos no se ve nada: el motor lo resuelve en milisegundos
haga lo que haga. Hace falta volumen para que el problema aparezca.

**Pasos.** Multiplica los pedidos existentes:

```sql
-- Tabla de trabajo con ~500.000 pedidos
SELECT TOP 0 * INTO dbo.pedidos_big FROM silver.pedidos;
GO

DECLARE @i INT = 0;
WHILE @i < 26          -- 19.270 x 26 ≈ 500.000
BEGIN
    INSERT INTO dbo.pedidos_big
    SELECT * FROM silver.pedidos;
    SET @i = @i + 1;
END
GO

SELECT COUNT(*) FROM dbo.pedidos_big;   -- ~500.000
```

Haz lo mismo con `silver.tickets` → `dbo.tickets_big`.

**⚠️ Si `id_pedido` es clave primaria**, crea `pedidos_big` sin la restricción o genera
ids nuevos con `ROW_NUMBER()`.

**✅ Debe salir:** `dbo.pedidos_big` con ~500.000 filas.

**📎 Evidencia:** `evidencia/sqlserver/05_volumen.txt`.

---

## SQL-06 · Medir la consulta original ⏱️ 30 min ⭐

**Pasos**

1. En el editor, activa estadísticas y plan:

```sql
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
```

2. Activa **Incluir plan de ejecución real** (Ctrl+M en SSMS).
3. Ejecuta la consulta **original** del enunciado contra `dbo.pedidos_big` y
   `dbo.tickets_big`, **sin índices**.
4. Captura: tiempo transcurrido, lecturas lógicas por tabla y el plan.

5. Ahora **con índices**, para aislar el efecto:

```sql
CREATE INDEX ix_big_fecha   ON dbo.pedidos_big (fecha_pedido)
       INCLUDE (id_cliente, valor_bruto, descuento);
CREATE INDEX ix_big_cliente ON dbo.pedidos_big (id_cliente);
CREATE INDEX ix_big_tk      ON dbo.tickets_big (id_cliente, fecha_creacion DESC)
       INCLUDE (canal);
```

Vuelve a ejecutar la original y captura de nuevo.

**✅ Lo que esperas encontrar (hipótesis a confirmar):** en el plan aparece un **Index
Scan** o **Table Scan** sobre tickets en vez de un **Index Seek**, porque el
`CAST(... AS VARCHAR(20))` en ambos lados del cruce **impide usar el índice**.

**📎 Evidencia:** `evidencia/sqlserver/06_original_plan.png`,
`06_original_stats.txt` (las dos variantes: sin y con índices).

---

## SQL-07 · Medir la consulta reescrita ⏱️ 30 min ⭐

**Pasos**

1. Ejecuta `sqlserver/optimizacion/02_optimizacion.sql` con las mismas estadísticas y
   el plan activado, sobre las mismas tablas grandes.
2. Captura tiempo, lecturas y plan.
3. **Comprueba que da el mismo resultado:**

```sql
-- Guarda ambos resultados en tablas temporales y compáralos
SELECT COUNT(*) FROM (
    SELECT * FROM #resultado_original
    EXCEPT
    SELECT * FROM #resultado_reescrita
) d;
-- Debe ser 0
```

4. Llena esta tabla con tus números:

| Variante | Tiempo | Lecturas lógicas | Operador sobre tickets |
|---|---:|---:|---|
| Original sin índices | | | |
| Original con índices | | | |
| **Reescrita con índices** | | | |

**Referencia del experimento en SQLite** (solo como forma del problema, no como tiempos
comparables): 500.000 pedidos → original con índices **199,18 s**, reescrita **0,08 s**.
Y con 100.000, quitar **solo** el CAST bajó de 7,28 s a 0,06 s.

**✅ Debe salir:** la reescrita mucho más rápida, con menos lecturas lógicas y un **Index
Seek** donde la original hacía *scan*, con resultados idénticos.

**📎 Evidencia:** `evidencia/sqlserver/07_reescrita_plan.png`,
`07_reescrita_stats.txt` y `07_comparacion.md` con la tabla llena.

**Cierra:** **E02**. Convierte «no medido en SQL Server» en un hecho con plan de
ejecución.

---

## SQL-08 · Usuario de solo lectura y reporte ODBC ⏱️ 30 min

**Por qué.** El PR revisado usaba `admin` con contraseña en el código. Esto cierra el
círculo con la práctica correcta.

**Pasos**

```sql
CREATE LOGIN reporte_ro WITH PASSWORD = 'Otra.Clave.Fuerte.2026';
CREATE USER  reporte_ro FOR LOGIN reporte_ro;
GRANT SELECT ON SCHEMA::gold TO reporte_ro;
-- Sin permisos sobre silver ni control
```

Prueba el reporte con ese usuario:

```bash
$env:DWH_CONNECTION_STRING = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=andina;UID=reporte_ro;PWD=Otra.Clave.Fuerte.2026;TrustServerCertificate=yes"
python src/shared/reporte_ventas.py
```

**✅ Debe salir:** el reporte imprime la venta por canal del día anterior. Y si intentas
`SELECT * FROM silver.pedidos` con ese usuario, debe **denegarte** el permiso.

**📎 Evidencia:** `evidencia/sqlserver/08_reporte.txt` **con la contraseña tapada**.

---

## SQL-09 · Limpiar ⏱️ 10 min

```sql
DROP TABLE IF EXISTS dbo.pedidos_big;
DROP TABLE IF EXISTS dbo.tickets_big;
```

```bash
docker stop sqlserver-andina
# Para borrarlo del todo:
# docker rm sqlserver-andina
```

**📎 Evidencia:** `evidencia/sqlserver/09_limpieza.txt`.

---

## Lista de cierre

| Tarea | Hecho | Evidencia | Cierra |
|---|---|---|---|
| SQL-01 Docker | ☐ | `01_docker.txt` | — |
| SQL-02 DDL | ☐ | `02_ddl.txt` | mitad de **E01** |
| SQL-03 Carga estrella | ☐ | `03_carga.txt` | **E01** |
| SQL-04 Venta y recompra | ☐ | `04_tsql.txt` + `04_diferencias.txt` | mitad de **E02** |
| SQL-05 Volumen | ☐ | `05_volumen.txt` | — |
| SQL-06 Plan original | ☐ | `06_original_plan.png` | — |
| SQL-07 Plan reescrito | ☐ | `07_comparacion.md` | **E02** |
| SQL-08 Solo lectura | ☐ | `08_reporte.txt` | higiene y P16 |
| SQL-09 Limpieza | ☐ | `09_limpieza.txt` | — |

**Lo que más me interesa de este bloque:** la lista de errores del DDL (SQL-02) y la
tabla de comparación de planes (SQL-07). Son los dos que convierten afirmaciones
escritas en hechos medidos.
