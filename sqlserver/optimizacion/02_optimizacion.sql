-- ============================================================================
-- Parte 1, punto 5 - Optimización de la consulta de 50 millones de pedidos (T-SQL)
-- Nota: no se ejecutó en SQL Server. La forma del problema se midió con
-- experimento_optimizacion.py (SQLite, datos sintéticos); ver docs/05_optimizacion.md.
-- ============================================================================

/* ---------------------------------------------------------------------------
   PROBLEMAS DE LA CONSULTA ORIGINAL
   1. Subconsulta correlacionada para venta_mes: se ejecuta una vez por cliente.
   2. YEAR(p.fecha_pedido) / MONTH(p.fecha_pedido): función sobre la columna; el índice por
      fecha no se puede usar (predicado no SARGable) y se lee la tabla completa.
   3. CAST(... AS VARCHAR(20)) en ambos lados del cruce con tickets_soporte: conversión
      sobre las dos columnas, ninguna búsqueda por índice. Ambos id_cliente ya son VARCHAR(9)
      (ver DDL): el CAST no aporta nada y es lo que más pesa.
   4. IN (SELECT DISTINCT ...): buena práctica, no causa de lentitud. El optimizador suele
      convertirlo en semiunión y descartar el DISTINCT; EXISTS expresa mejor la intención.
   5. TOP 1 ... ORDER BY fecha_creacion DESC sin índice (id_cliente, fecha_creacion DESC):
      ordena los tickets del cliente en cada ejecución.
   6. GETDATE(): SQL Server lo evalúa una vez por consulta, no por fila; se pasa a una
      variable para que el rango del mes sea explícito y se pueda probar con otra fecha.
   7. Observación de negocio: el original suma TODOS los estados del mes (también devueltos y
      cancelados). La reescritura conserva ese resultado para ser equivalente; si la intención
      es venta neta, añade AND p.estado = 'ENTREGADO' (se señala abajo).
--------------------------------------------------------------------------- */

-- CONSULTA REESCRITA (mismo resultado que la original)
DECLARE @ini DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
DECLARE @fin DATE = DATEADD(MONTH, 1, @ini);

WITH venta AS (
    SELECT p.id_cliente,
           SUM(p.valor_bruto - p.descuento) AS venta_mes
    FROM dbo.pedidos AS p
    WHERE p.fecha_pedido >= @ini
      AND p.fecha_pedido <  @fin          -- rango SARGable: usa el índice por fecha
      -- AND p.estado = 'ENTREGADO'       -- descomentar si se quiere venta neta (ver punto 7)
    GROUP BY p.id_cliente
)
SELECT c.id_cliente,
       v.venta_mes,
       u.canal AS ultimo_canal_soporte
FROM dbo.clientes AS c
LEFT JOIN venta AS v ON v.id_cliente = c.id_cliente
OUTER APPLY (
    SELECT TOP (1) t.canal
    FROM dbo.tickets_soporte AS t
    WHERE t.id_cliente = c.id_cliente     -- mismo tipo a ambos lados: búsqueda por índice
    ORDER BY t.fecha_creacion DESC
) AS u
WHERE EXISTS (
    SELECT 1 FROM dbo.pedidos AS d
    WHERE d.id_cliente = c.id_cliente AND d.estado = 'DEVUELTO'
)
ORDER BY v.venta_mes DESC;
GO

-- ÍNDICES
-- Ventas del mes: lectura por rango de fechas, sin ir a la tabla (cubre todas las columnas).
CREATE INDEX ix_pedidos_fecha
    ON dbo.pedidos (fecha_pedido)
    INCLUDE (id_cliente, valor_bruto, descuento);

-- Pedidos devueltos: índice filtrado, pequeño, solo con las filas que interesan al EXISTS.
CREATE INDEX ix_pedidos_devueltos
    ON dbo.pedidos (id_cliente)
    WHERE estado = 'DEVUELTO';

-- Último canal de soporte: la búsqueda del TOP 1 entra directo a la fila más reciente.
CREATE INDEX ix_tickets_cliente_fecha
    ON dbo.tickets_soporte (id_cliente, fecha_creacion DESC)
    INCLUDE (canal);
GO

-- PARTICIONES (50M de filas)
-- Partición mensual por fecha_pedido: la consulta del mes en curso toca una sola partición
-- (eliminación de particiones) y el archivado de meses antiguos es un SWITCH, no un DELETE.
-- Es un beneficio sobre todo de mantenimiento; la velocidad de esta consulta la dan los índices.
CREATE PARTITION FUNCTION pf_pedidos_mes (DATETIME2)
AS RANGE RIGHT FOR VALUES ('2025-01-01', '2025-02-01', '2025-03-01' /* ... un valor por mes ... */);
CREATE PARTITION SCHEME ps_pedidos_mes
AS PARTITION pf_pedidos_mes ALL TO ([PRIMARY]);
-- La tabla pasa a usar: CREATE CLUSTERED INDEX cx_pedidos ON dbo.pedidos (fecha_pedido, id_pedido)
--                       ON ps_pedidos_mes (fecha_pedido);
-- Los índices anteriores se crean alineados (ON ps_pedidos_mes (fecha_pedido)).
-- Alternativa para analítica: índice columnstore no agrupado sobre pedidos.
GO
