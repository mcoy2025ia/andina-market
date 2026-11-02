"""Modelo estrella local con nombres de consumo SQL/DAX. No despliega SQL Server.

Dimensiones con claves estables, hechos reconstruidos en la transacción del ETL.
La recarga de hechos prioriza auditabilidad para el tamaño del caso; no se presenta
como carga de hechos incremental a escala.
"""

from . import etiquetas

SCHEMA = '''CREATE SCHEMA IF NOT EXISTS gold;
CREATE TABLE IF NOT EXISTS gold.dim_fecha (
fecha_key INTEGER PRIMARY KEY, fecha DATE UNIQUE, anio SMALLINT, trimestre SMALLINT,
mes SMALLINT, nombre_mes VARCHAR, anio_mes VARCHAR, dia_semana SMALLINT, es_fin_de_semana BOOLEAN);
CREATE TABLE IF NOT EXISTS gold.dim_canal (canal_key INTEGER PRIMARY KEY, canal VARCHAR UNIQUE);
CREATE TABLE IF NOT EXISTS gold.dim_categoria (categoria_key INTEGER PRIMARY KEY, categoria VARCHAR UNIQUE);
CREATE TABLE IF NOT EXISTS gold.dim_cliente (cliente_key INTEGER PRIMARY KEY, id_cliente VARCHAR UNIQUE,
id_cliente_maestro VARCHAR, nombre VARCHAR, ciudad VARCHAR, canal_registro VARCHAR,
fecha_registro DATE, cohorte_registro DATE);
CREATE TABLE IF NOT EXISTS gold.fact_pedido (id_pedido VARCHAR PRIMARY KEY, cliente_key INTEGER,
fecha_key INTEGER, canal_key INTEGER, categoria_key INTEGER, valor_bruto BIGINT, descuento BIGINT,
venta_neta BIGINT, estado VARCHAR, cuenta_como_venta BOOLEAN, fecha_entrega DATE);
CREATE TABLE IF NOT EXISTS gold.fact_pago (id_pago VARCHAR PRIMARY KEY, id_pedido VARCHAR,
fecha_key INTEGER, medio_pago VARCHAR, valor BIGINT, es_reembolso BOOLEAN);
CREATE TABLE IF NOT EXISTS gold.fact_venta_neta_diaria (fecha_key INTEGER, canal_key INTEGER,
categoria_key INTEGER, num_pedidos INTEGER, venta_bruta BIGINT, descuento BIGINT, venta_neta BIGINT,
PRIMARY KEY(fecha_key,canal_key,categoria_key));
-- tipo_caso solo lleva decisiones humanas; la salida de un clasificador vive en
-- tipo_caso_propuesto. Separarlas evita que una propuesta se lea como validada.
CREATE TABLE IF NOT EXISTS gold.fact_ticket (id_ticket VARCHAR PRIMARY KEY, cliente_key INTEGER,
id_pedido VARCHAR, fecha_creacion_key INTEGER, canal_soporte VARCHAR, estado VARCHAR,
tipo_caso VARCHAR, tipo_caso_propuesto VARCHAR, clasificacion_estado VARCHAR,
clasificacion_version VARCHAR, horas_resolucion DOUBLE);'''


def refrescar_estrella(con, cfg):
    con.execute(SCHEMA)
    for nombre in ('canal', 'categoria'):
        con.execute(f'''INSERT INTO gold.dim_{nombre}
            SELECT (SELECT coalesce(max({nombre}_key),0) FROM gold.dim_{nombre})
                + row_number() OVER (ORDER BY p.{nombre}), p.{nombre}
            FROM (SELECT DISTINCT {nombre} FROM silver_pedidos) p
            WHERE NOT EXISTS (SELECT 1 FROM gold.dim_{nombre} d WHERE d.{nombre}=p.{nombre})''')
    con.execute("INSERT INTO gold.dim_cliente SELECT 0,'DESCONOCIDO','DESCONOCIDO',NULL,NULL,NULL,NULL,NULL "
                "WHERE NOT EXISTS (SELECT 1 FROM gold.dim_cliente WHERE cliente_key=0)")
    con.execute('''INSERT INTO gold.dim_cliente
        SELECT (SELECT coalesce(max(cliente_key),0) FROM gold.dim_cliente)
            + row_number() OVER (ORDER BY c.id_cliente), c.id_cliente,m.id_cliente_maestro,
            c.nombre,c.ciudad,c.canal_registro,c.fecha_registro,c.cohorte_registro
        FROM silver_clientes c JOIN v_cliente_maestro m USING(id_cliente)
        WHERE NOT EXISTS (SELECT 1 FROM gold.dim_cliente d WHERE d.id_cliente=c.id_cliente)''')
    con.execute('''UPDATE gold.dim_cliente d SET id_cliente_maestro=m.id_cliente_maestro,
        nombre=c.nombre, ciudad=c.ciudad, canal_registro=c.canal_registro,
        fecha_registro=c.fecha_registro, cohorte_registro=c.cohorte_registro
        FROM silver_clientes c JOIN v_cliente_maestro m USING(id_cliente)
        WHERE d.id_cliente=c.id_cliente''')
    con.execute('''CREATE OR REPLACE TEMP VIEW fechas_modelo AS
        SELECT fecha_pedido_dia AS fecha FROM silver_pedidos UNION
        SELECT fecha_pago FROM silver_pagos UNION
        SELECT cast(fecha_creacion AS DATE) FROM silver_tickets''')
    desde, hasta = con.execute("SELECT least(coalesce(min(fecha),?),?), "
                               "greatest(coalesce(max(fecha),?),?) FROM fechas_modelo",
                               [cfg.fecha_min,cfg.fecha_min,cfg.fecha_max,cfg.fecha_max]).fetchone()
    # Años completos: la medida DAX limita las fechas comparables con tiene_datos.
    desde, hasta = desde.replace(month=1, day=1), hasta.replace(month=12, day=31)
    con.execute('''INSERT INTO gold.dim_fecha
        SELECT cast(strftime(d,'%Y%m%d') AS INTEGER),cast(d AS DATE),year(d),quarter(d),month(d),
        list_extract(['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
        'septiembre','octubre','noviembre','diciembre'],month(d)),strftime(d,'%Y-%m'),
        isodow(d),isodow(d)>=6 FROM generate_series(?::DATE,?::DATE,INTERVAL 1 DAY) g(d)
        WHERE NOT EXISTS (SELECT 1 FROM gold.dim_fecha f WHERE f.fecha=cast(g.d AS DATE))''', [desde,hasta])
    for tabla in ('fact_pago','fact_ticket','fact_pedido','fact_venta_neta_diaria'):
        con.execute(f'DELETE FROM gold.{tabla}')
    con.execute('''INSERT INTO gold.fact_pedido
        SELECT p.id_pedido, CASE WHEN s.id_cliente IS NULL THEN 0 ELSE c.cliente_key END,
        f.fecha_key,can.canal_key,cat.categoria_key,p.valor_bruto,p.descuento,
        CASE WHEN p.estado='ENTREGADO' THEN p.valor_neto ELSE 0 END,
        p.estado,p.estado='ENTREGADO',p.fecha_entrega
        FROM silver_pedidos p LEFT JOIN silver_clientes s ON s.id_cliente=p.id_cliente
        LEFT JOIN gold.dim_cliente c ON c.id_cliente=s.id_cliente
        JOIN gold.dim_fecha f ON f.fecha=p.fecha_pedido_dia
        JOIN gold.dim_canal can ON can.canal=p.canal
        JOIN gold.dim_categoria cat ON cat.categoria=p.categoria''')
    con.execute('''INSERT INTO gold.fact_pago
        SELECT p.id_pago,p.id_pedido,f.fecha_key,p.medio_pago,p.valor,p.es_reembolso
        FROM silver_pagos p JOIN gold.dim_fecha f ON f.fecha=p.fecha_pago
        JOIN gold.fact_pedido o ON o.id_pedido=p.id_pedido''')
    con.execute('''INSERT INTO gold.fact_venta_neta_diaria
        SELECT f.fecha_key,c.canal_key,k.categoria_key,g.num_pedidos,g.venta_bruta,g.descuento,g.venta_neta
        FROM gold_venta_neta_diaria g JOIN gold.dim_fecha f ON f.fecha=g.fecha
        JOIN gold.dim_canal c ON c.canal=g.canal JOIN gold.dim_categoria k ON k.categoria=g.categoria''')
    # tipo_caso sale de v_etiqueta_vigente.tipo_revisado, que por construcción solo
    # contiene decisiones humanas: no hay forma de publicar una propuesta como validada.
    con.execute(etiquetas.ESQUEMA)
    con.execute('''INSERT INTO gold.fact_ticket
        SELECT t.id_ticket,CASE WHEN s.id_cliente IS NULL THEN 0 ELSE c.cliente_key END,
        t.id_pedido,f.fecha_key,t.canal_soporte,t.estado,
        e.tipo_revisado, e.tipo_propuesto,
        CASE WHEN e.tipo_revisado IS NOT NULL THEN 'REVISADA'
             WHEN e.tipo_propuesto IS NOT NULL THEN 'PROPUESTA' END,
        coalesce(e.version_revisada, e.version_propuesta),
        t.horas_resolucion
        FROM silver_tickets t LEFT JOIN silver_clientes s ON s.id_cliente=t.id_cliente
        LEFT JOIN gold.dim_cliente c ON c.id_cliente=s.id_cliente
        LEFT JOIN v_etiqueta_vigente e ON e.texto_hash=t.texto_hash
        JOIN gold.dim_fecha f ON f.fecha=cast(t.fecha_creacion AS DATE)''')
    counts = {}
    for fact, silver in [('fact_pedido','silver_pedidos'),('fact_pago','silver_pagos'),
                         ('fact_ticket','silver_tickets'),('fact_venta_neta_diaria','gold_venta_neta_diaria')]:
        n = con.execute(f'SELECT count(*) FROM gold.{fact}').fetchone()[0]
        if n != con.execute(f'SELECT count(*) FROM {silver}').fetchone()[0]:
            raise RuntimeError(f'Modelo estrella pierde filas: {fact}')
        counts[fact] = n
    total, nulos = con.execute('SELECT coalesce(sum(venta_neta),0),count(*) FILTER '
                              '(WHERE cliente_key IS NULL) FROM gold.fact_pedido').fetchone()
    if nulos or total != con.execute('SELECT coalesce(sum(venta_neta),0) FROM gold_venta_neta_diaria').fetchone()[0]:
        raise RuntimeError('Modelo estrella no concilia')
    return counts
