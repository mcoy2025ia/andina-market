-- ============================================================================
-- Parte 1, punto 1 - T-SQL (SQL Server / Fabric Warehouse)
-- Esquema: silver.pedidos, silver.clientes, silver.v_cliente_maestro (ver ddl_tsql.sql)
-- Definiciones:
--   venta neta    = valor_bruto - descuento, solo estado ENTREGADO, por fecha_pedido
--   persona       = id_cliente_maestro (une los clientes duplicados por documento)
--   cohorte       = mes de registro más antiguo de la persona
--   primer pedido = primer pedido ENTREGADO de la persona (por fecha)
--   recompra N    = otro pedido ENTREGADO en fecha posterior y dentro de N meses calendario del primero
--   madurez       = solo cuenta a la persona si primer_pedido + N meses <= última fecha de datos
-- Nota: no se ejecutó contra un SQL Server real; la lógica se validó en DuckDB (ver duckdb/).
-- ============================================================================

-- A) Venta neta mensual por canal con variación frente al mes anterior
;WITH mensual AS (
    SELECT DATEFROMPARTS(YEAR(fecha_pedido_dia), MONTH(fecha_pedido_dia), 1) AS mes,
           canal,
           SUM(valor_neto) AS venta_neta,
           COUNT(*)        AS pedidos
    FROM silver.pedidos
    WHERE estado = 'ENTREGADO'
    GROUP BY DATEFROMPARTS(YEAR(fecha_pedido_dia), MONTH(fecha_pedido_dia), 1), canal
), con_anterior AS (
    SELECT mes, canal, pedidos, venta_neta,
           LAG(venta_neta) OVER (PARTITION BY canal ORDER BY mes) AS venta_mes_anterior
    FROM mensual
)
SELECT mes, canal, pedidos, venta_neta, venta_mes_anterior,
       ROUND(100.0 * (venta_neta - venta_mes_anterior) / NULLIF(venta_mes_anterior, 0), 2) AS variacion_pct
FROM con_anterior
ORDER BY canal, mes;

-- B) Recompra por cohorte de registro a 1, 3 y 6 meses
;WITH personas AS (
    SELECT m.id_cliente_maestro AS persona, MIN(c.cohorte_registro) AS cohorte
    FROM silver.clientes c
    JOIN silver.v_cliente_maestro m ON m.id_cliente = c.id_cliente
    GROUP BY m.id_cliente_maestro
), entregados AS (
    SELECT m.id_cliente_maestro AS persona, p.fecha_pedido_dia AS fecha
    FROM silver.pedidos p
    JOIN silver.v_cliente_maestro m ON m.id_cliente = p.id_cliente
    WHERE p.estado = 'ENTREGADO'
), primer AS (
    SELECT persona, MIN(fecha) AS fecha_primero FROM entregados GROUP BY persona
), ventanas AS (
    SELECT pr.persona, pr.fecha_primero,
           MAX(CASE WHEN e.fecha > pr.fecha_primero AND e.fecha <= DATEADD(MONTH, 1, pr.fecha_primero) THEN 1 ELSE 0 END) AS r1,
           MAX(CASE WHEN e.fecha > pr.fecha_primero AND e.fecha <= DATEADD(MONTH, 3, pr.fecha_primero) THEN 1 ELSE 0 END) AS r3,
           MAX(CASE WHEN e.fecha > pr.fecha_primero AND e.fecha <= DATEADD(MONTH, 6, pr.fecha_primero) THEN 1 ELSE 0 END) AS r6
    FROM primer pr
    JOIN entregados e ON e.persona = pr.persona
    GROUP BY pr.persona, pr.fecha_primero
), limite AS (
    SELECT MAX(fecha_pedido_dia) AS ultima FROM silver.pedidos
)
SELECT p.cohorte,
       COUNT(*)         AS personas_cohorte,
       COUNT(v.persona) AS compradores,
       SUM(CASE WHEN DATEADD(MONTH, 1, v.fecha_primero) <= l.ultima THEN 1 ELSE 0 END)       AS base_1m,
       SUM(CASE WHEN DATEADD(MONTH, 1, v.fecha_primero) <= l.ultima THEN v.r1  ELSE 0 END)  AS recompra_1m,
       ROUND(100.0 * SUM(CASE WHEN DATEADD(MONTH, 1, v.fecha_primero) <= l.ultima THEN v.r1  ELSE 0 END)
             / NULLIF(SUM(CASE WHEN DATEADD(MONTH, 1, v.fecha_primero) <= l.ultima THEN 1 ELSE 0 END), 0), 2) AS tasa_1m,
       SUM(CASE WHEN DATEADD(MONTH, 3, v.fecha_primero) <= l.ultima THEN 1 ELSE 0 END)       AS base_3m,
       SUM(CASE WHEN DATEADD(MONTH, 3, v.fecha_primero) <= l.ultima THEN v.r3  ELSE 0 END)  AS recompra_3m,
       ROUND(100.0 * SUM(CASE WHEN DATEADD(MONTH, 3, v.fecha_primero) <= l.ultima THEN v.r3  ELSE 0 END)
             / NULLIF(SUM(CASE WHEN DATEADD(MONTH, 3, v.fecha_primero) <= l.ultima THEN 1 ELSE 0 END), 0), 2) AS tasa_3m,
       SUM(CASE WHEN DATEADD(MONTH, 6, v.fecha_primero) <= l.ultima THEN 1 ELSE 0 END)       AS base_6m,
       SUM(CASE WHEN DATEADD(MONTH, 6, v.fecha_primero) <= l.ultima THEN v.r6 ELSE 0 END)  AS recompra_6m,
       ROUND(100.0 * SUM(CASE WHEN DATEADD(MONTH, 6, v.fecha_primero) <= l.ultima THEN v.r6 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN DATEADD(MONTH, 6, v.fecha_primero) <= l.ultima THEN 1 ELSE 0 END), 0), 2) AS tasa_6m
FROM personas p
LEFT JOIN ventanas v ON v.persona = p.persona
CROSS JOIN limite l
GROUP BY p.cohorte
ORDER BY p.cohorte;
