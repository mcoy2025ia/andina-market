-- ============================================================================
-- Parte 1, punto 1 - Spark SQL (Fabric Lakehouse y Databricks)
-- Misma lógica que sqlserver/01_ventas_recompra.sql; solo cambia el dialecto.
-- Tablas Silver: {S}clientes, {S}pedidos (las crea el notebook andina_etl_spark).
-- Definiciones:
--   venta neta    = valor_bruto - descuento, solo estado ENTREGADO, por fecha_pedido
--   persona       = id_cliente_maestro (une los clientes duplicados por documento)
--   cohorte       = mes de registro más antiguo de la persona
--   primer pedido = primer pedido ENTREGADO de la persona (por fecha)
--   recompra N    = otro pedido ENTREGADO en fecha posterior y dentro de N meses calendario del primero
--   madurez       = solo cuenta a la persona si primer_pedido + N meses <= última fecha de datos
-- No se ejecutó en Fabric ni en Databricks; sí en Spark 3.5 local (ver tests/test_sql_spark.py).
-- ============================================================================

-- 0) Vista de cliente maestro (en SQL Server y DuckDB ya existe como vista)
CREATE OR REPLACE TEMP VIEW v_cliente_maestro AS
SELECT id_cliente,
       MIN(id_cliente) OVER (PARTITION BY COALESCE(documento_limpio, id_cliente)) AS id_cliente_maestro
FROM {S}clientes;

-- A) Calendario completo del contrato del caso: enero 2025 a septiembre 2026.
-- Sin venta: cero; previo cero o inexistente: variacion NULL.
WITH meses AS (SELECT explode(sequence(DATE '2025-01-01',DATE '2026-09-01',INTERVAL 1 MONTH)) AS mes),
canales AS (SELECT 'APP' AS canal UNION SELECT 'WEB' UNION SELECT 'TIENDA'
            UNION SELECT DISTINCT canal FROM {S}pedidos),
mensual AS (
    SELECT CAST(date_trunc('month', fecha_pedido_dia) AS DATE) AS mes, canal, SUM(valor_neto) AS venta_neta, COUNT(*) AS pedidos
    FROM {S}pedidos WHERE estado = 'ENTREGADO' GROUP BY CAST(date_trunc('month', fecha_pedido_dia) AS DATE), canal
), completo AS (
    SELECT m.mes,c.canal,COALESCE(v.pedidos,0) AS pedidos,COALESCE(v.venta_neta,0) AS venta_neta
    FROM meses m CROSS JOIN canales c LEFT JOIN mensual v ON v.mes=m.mes AND v.canal=c.canal
), con_anterior AS (
    SELECT *,LAG(venta_neta) OVER (PARTITION BY canal ORDER BY mes) AS venta_mes_anterior FROM completo
)
SELECT mes,canal,pedidos,venta_neta,venta_mes_anterior,
       ROUND(100.0*(venta_neta-venta_mes_anterior)/NULLIF(venta_mes_anterior,0),2) AS variacion_pct
FROM con_anterior ORDER BY canal,mes;

-- B) Recompra por cohorte de registro a 1, 3 y 6 meses
WITH personas AS (
    SELECT m.id_cliente_maestro AS persona, MIN(c.cohorte_registro) AS cohorte
    FROM {S}clientes c
    JOIN v_cliente_maestro m ON m.id_cliente = c.id_cliente
    GROUP BY m.id_cliente_maestro
), entregados AS (
    SELECT m.id_cliente_maestro AS persona, p.fecha_pedido_dia AS fecha
    FROM {S}pedidos p
    JOIN v_cliente_maestro m ON m.id_cliente = p.id_cliente
    WHERE p.estado = 'ENTREGADO'
), primer AS (
    SELECT persona, MIN(fecha) AS fecha_primero FROM entregados GROUP BY persona
), ventanas AS (
    SELECT pr.persona, pr.fecha_primero,
           MAX(CASE WHEN e.fecha > pr.fecha_primero AND e.fecha <= add_months(pr.fecha_primero, 1)  THEN 1 ELSE 0 END) AS r1,
           MAX(CASE WHEN e.fecha > pr.fecha_primero AND e.fecha <= add_months(pr.fecha_primero, 3)  THEN 1 ELSE 0 END) AS r3,
           MAX(CASE WHEN e.fecha > pr.fecha_primero AND e.fecha <= add_months(pr.fecha_primero, 6) THEN 1 ELSE 0 END) AS r6
    FROM primer pr
    JOIN entregados e ON e.persona = pr.persona
    GROUP BY pr.persona, pr.fecha_primero
), limite AS (
    SELECT MAX(fecha_pedido_dia) AS ultima FROM {S}pedidos
)
SELECT p.cohorte,
       COUNT(*)         AS personas_cohorte,
       COUNT(v.persona) AS compradores,
       SUM(CASE WHEN add_months(v.fecha_primero, 1)  <= l.ultima THEN 1 ELSE 0 END)       AS base_1m,
       SUM(CASE WHEN add_months(v.fecha_primero, 1)  <= l.ultima THEN v.r1  ELSE 0 END)  AS recompra_1m,
       ROUND(100.0 * SUM(CASE WHEN add_months(v.fecha_primero, 1)  <= l.ultima THEN v.r1  ELSE 0 END)
             / NULLIF(SUM(CASE WHEN add_months(v.fecha_primero, 1)  <= l.ultima THEN 1 ELSE 0 END), 0), 2) AS tasa_1m,
       SUM(CASE WHEN add_months(v.fecha_primero, 3)  <= l.ultima THEN 1 ELSE 0 END)       AS base_3m,
       SUM(CASE WHEN add_months(v.fecha_primero, 3)  <= l.ultima THEN v.r3  ELSE 0 END)  AS recompra_3m,
       ROUND(100.0 * SUM(CASE WHEN add_months(v.fecha_primero, 3)  <= l.ultima THEN v.r3  ELSE 0 END)
             / NULLIF(SUM(CASE WHEN add_months(v.fecha_primero, 3)  <= l.ultima THEN 1 ELSE 0 END), 0), 2) AS tasa_3m,
       SUM(CASE WHEN add_months(v.fecha_primero, 6) <= l.ultima THEN 1 ELSE 0 END)       AS base_6m,
       SUM(CASE WHEN add_months(v.fecha_primero, 6) <= l.ultima THEN v.r6 ELSE 0 END)  AS recompra_6m,
       ROUND(100.0 * SUM(CASE WHEN add_months(v.fecha_primero, 6) <= l.ultima THEN v.r6 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN add_months(v.fecha_primero, 6) <= l.ultima THEN 1 ELSE 0 END), 0), 2) AS tasa_6m
FROM personas p
LEFT JOIN ventanas v ON v.persona = p.persona
CROSS JOIN limite l
GROUP BY p.cohorte
ORDER BY p.cohorte;
