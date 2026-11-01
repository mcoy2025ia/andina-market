/* =====================================================================
   Andina Market - DDL del modelo (SQL Server / Fabric Warehouse)
   Capas: silver (entidades limpias), control (cuarentena y ejecución),
          gold (esquema estrella).
   El ETL de este repositorio corre sobre DuckDB con el mismo modelo;
   este script es el destino en SQL Server.
   Decisiones: venta atribuida a fecha_pedido; venta neta = ENTREGADO;
   DEVUELTO no es venta; pedidos fuera de rango van a cuarentena.
   ===================================================================== */

IF SCHEMA_ID('silver')  IS NULL EXEC('CREATE SCHEMA silver');
IF SCHEMA_ID('control') IS NULL EXEC('CREATE SCHEMA control');
IF SCHEMA_ID('gold')    IS NULL EXEC('CREATE SCHEMA gold');
GO

/* ------------------------------ SILVER ------------------------------ */

CREATE TABLE silver.clientes (
    id_cliente          VARCHAR(9)    NOT NULL,
    nombre              NVARCHAR(120) NOT NULL,
    documento_original  VARCHAR(20)   NULL,          -- tal como llega
    documento_limpio    VARCHAR(15)   NULL,          -- solo dígitos, sin ceros a la izquierda
    ciudad              NVARCHAR(40)  NULL,
    canal_registro      VARCHAR(12)   NULL,
    fecha_registro      DATE          NOT NULL,
    cohorte_registro    DATE          NULL,          -- primer día del mes de registro
    row_hash            CHAR(64)      NOT NULL,
    ingested_at         DATETIME2(0)  NOT NULL CONSTRAINT df_cli_ing DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_silver_clientes PRIMARY KEY (id_cliente),
    CONSTRAINT ck_cli_canal CHECK (canal_registro IN ('WEB','APP','TIENDA'))
);
CREATE INDEX ix_cli_documento ON silver.clientes (documento_limpio) INCLUDE (id_cliente);
CREATE INDEX ix_cli_cohorte   ON silver.clientes (cohorte_registro);
GO

CREATE TABLE silver.pedidos (
    id_pedido                 VARCHAR(11)    NOT NULL,
    id_cliente                VARCHAR(9)     NULL,    -- FK lógica: 60 pedidos con cliente inexistente
    fecha_pedido              DATETIME2(0)   NOT NULL,
    fecha_pedido_dia          DATE           NOT NULL, -- fecha de atribución de la venta
    canal                     VARCHAR(12)    NOT NULL,
    categoria                 NVARCHAR(30)   NOT NULL,
    valor_bruto               DECIMAL(18,0)  NOT NULL,
    descuento                 DECIMAL(18,0)  NOT NULL,
    valor_neto                DECIMAL(18,0)  NOT NULL,
    estado                    VARCHAR(10)    NOT NULL,
    fecha_entrega             DATE           NULL,
    flag_cliente_desconocido  BIT            NOT NULL CONSTRAINT df_ped_cli DEFAULT 0,
    hash_negocio              CHAR(64)       NULL,
    row_hash                  CHAR(64)       NOT NULL,
    ingested_at               DATETIME2(0)   NOT NULL CONSTRAINT df_ped_ing DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_silver_pedidos PRIMARY KEY (id_pedido),
    CONSTRAINT ck_ped_canal  CHECK (canal IN ('WEB','APP','TIENDA')),
    CONSTRAINT ck_ped_estado CHECK (estado IN ('ENTREGADO','DEVUELTO','CANCELADO')),
    CONSTRAINT ck_ped_valor  CHECK (valor_bruto > 0 AND descuento >= 0 AND descuento <= valor_bruto),
    CONSTRAINT ck_ped_neto   CHECK (valor_neto = valor_bruto - descuento)
);
-- Soporte de las consultas de cliente/mes y de venta por día, canal y estado.
CREATE INDEX ix_ped_cliente_dia ON silver.pedidos (id_cliente, fecha_pedido_dia)
    INCLUDE (valor_neto, estado);
CREATE INDEX ix_ped_dia_canal   ON silver.pedidos (fecha_pedido_dia, canal, estado)
    INCLUDE (categoria, valor_bruto, descuento, valor_neto);
CREATE INDEX ix_ped_negocio     ON silver.pedidos (hash_negocio);
GO

CREATE TABLE silver.pagos (
    id_pago       VARCHAR(11)   NOT NULL,
    id_pedido     VARCHAR(11)   NOT NULL,
    fecha_pago    DATE          NOT NULL,      -- ya normalizada (yyyy-mm-dd y dd/mm/yyyy)
    valor         DECIMAL(18,0) NOT NULL,      -- negativo = reembolso
    es_reembolso  BIT           NOT NULL,
    medio_pago    NVARCHAR(20)  NOT NULL,
    fecha_carga   DATE          NOT NULL,      -- watermark de la carga incremental
    hash_negocio  CHAR(64)      NULL,
    row_hash      CHAR(64)      NOT NULL,
    ingested_at   DATETIME2(0)  NOT NULL CONSTRAINT df_pag_ing DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_silver_pagos PRIMARY KEY (id_pago),
    CONSTRAINT fk_pag_pedido FOREIGN KEY (id_pedido) REFERENCES silver.pedidos (id_pedido),
    CONSTRAINT ck_pag_valor  CHECK (valor <> 0),
    CONSTRAINT ck_pag_reemb  CHECK ((valor < 0 AND es_reembolso = 1) OR (valor > 0 AND es_reembolso = 0))
);
CREATE INDEX ix_pag_pedido  ON silver.pagos (id_pedido, fecha_pago) INCLUDE (valor);
CREATE INDEX ix_pag_carga   ON silver.pagos (fecha_carga);
CREATE INDEX ix_pag_negocio ON silver.pagos (hash_negocio);
GO

CREATE TABLE silver.tickets (
    id_ticket                 VARCHAR(10)   NOT NULL,
    id_cliente                VARCHAR(9)    NOT NULL,
    id_pedido                 VARCHAR(11)   NOT NULL,     -- FK lógica: 32 tickets apuntan a pedidos en cuarentena
    fecha_creacion            DATETIME2(0)  NOT NULL,
    canal_soporte             NVARCHAR(10)  NULL,
    estado                    VARCHAR(10)   NOT NULL,
    fecha_cierre              DATETIME2(0)  NULL,
    descripcion_original      NVARCHAR(100) NULL,
    descripcion_normalizada   NVARCHAR(100) NULL,
    tipo_caso                 NVARCHAR(40)  NULL,   -- salida de la clasificación con IA
    flag_cierre_invalido      BIT NOT NULL CONSTRAINT df_tk_ci DEFAULT 0,  -- cierre < creación
    flag_cerrado_sin_fecha    BIT NOT NULL CONSTRAINT df_tk_cf DEFAULT 0,
    flag_cliente_no_coincide  BIT NOT NULL CONSTRAINT df_tk_cn DEFAULT 0,
    row_hash                  CHAR(64)      NULL,
    ingested_at               DATETIME2(0)  NOT NULL CONSTRAINT df_tk_ing DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_silver_tickets PRIMARY KEY (id_ticket),
    CONSTRAINT fk_tk_cliente FOREIGN KEY (id_cliente) REFERENCES silver.clientes (id_cliente)
);
CREATE INDEX ix_tk_cliente ON silver.tickets (id_cliente, fecha_creacion DESC) INCLUDE (canal_soporte);
GO

-- Un mismo documento bajo dos id_cliente es la misma persona (40 casos en los datos).
CREATE VIEW silver.v_cliente_maestro AS
SELECT id_cliente,
       MIN(id_cliente) OVER (PARTITION BY COALESCE(documento_limpio, id_cliente)) AS id_cliente_maestro
FROM silver.clientes;
GO

/* ------------------------------ CONTROL ----------------------------- */

CREATE TABLE control.map_canal (
    valor_origen    VARCHAR(30) NOT NULL,   -- 'app', 'APLICACION', 'web ', 'PAGINA WEB', 'TIENDA FISICA'...
    canal_canonico  VARCHAR(12) NOT NULL,
    CONSTRAINT pk_map_canal PRIMARY KEY (valor_origen),
    CONSTRAINT ck_map_canal CHECK (canal_canonico IN ('WEB','APP','TIENDA'))
);
INSERT INTO control.map_canal (valor_origen, canal_canonico) VALUES
 ('WEB','WEB'),('PAGINA WEB','WEB'),('APP','APP'),('APLICACION','APP'),
 ('TIENDA','TIENDA'),('TIENDA FISICA','TIENDA');
GO

CREATE TABLE control.etl_run_log (
    run_id                VARCHAR(36)  NOT NULL,
    inicio                DATETIME2(0) NULL,
    fin                   DATETIME2(0) NULL,
    estado                VARCHAR(10)  NULL,      -- OK / FALLIDO
    filas_leidas          INT NULL,
    filas_validas         INT NULL,
    filas_cuarentena      INT NULL,
    filas_insertadas      INT NULL,
    filas_actualizadas    INT NULL,
    filas_sin_cambios     INT NULL,
    CONSTRAINT pk_etl_run_log PRIMARY KEY (run_id)
);

CREATE TABLE control.etl_watermark (
    tabla           VARCHAR(30)  NOT NULL,
    ultimo_valor    DATE         NOT NULL,        -- máxima fecha_carga procesada
    ultimo_run_id   VARCHAR(36)  NULL,
    actualizado_en  DATETIME2(0) NULL,
    CONSTRAINT pk_etl_watermark PRIMARY KEY (tabla),
    CONSTRAINT fk_wm_run FOREIGN KEY (ultimo_run_id) REFERENCES control.etl_run_log (run_id)
);

-- Una fila por (registro, regla violada). Reprocesar el mismo archivo no duplica filas.
CREATE TABLE control.cuarentena (
    tabla_origen   VARCHAR(30)    NOT NULL,
    id_registro    VARCHAR(20)    NOT NULL,
    regla_violada  VARCHAR(40)    NOT NULL,
    row_hash       CHAR(64)       NOT NULL,
    registro_json  NVARCHAR(MAX)  NOT NULL,       -- fila original completa
    run_id         VARCHAR(36)    NOT NULL,
    fecha_proceso  DATETIME2(0)   NOT NULL,
    CONSTRAINT pk_cuarentena PRIMARY KEY (tabla_origen, id_registro, regla_violada, row_hash),
    CONSTRAINT fk_cuar_run FOREIGN KEY (run_id) REFERENCES control.etl_run_log (run_id)
);
CREATE INDEX ix_cuar_regla ON control.cuarentena (tabla_origen, regla_violada);
GO

/* -------------------------------- GOLD ------------------------------ */

CREATE TABLE gold.dim_fecha (
    fecha_key         INT          NOT NULL,      -- yyyymmdd
    fecha             DATE         NOT NULL,
    anio              SMALLINT     NOT NULL,
    trimestre         TINYINT      NOT NULL,
    mes               TINYINT      NOT NULL,
    nombre_mes        VARCHAR(15)  NOT NULL,
    anio_mes          CHAR(7)      NOT NULL,
    dia_semana        TINYINT      NOT NULL,
    es_fin_de_semana  BIT          NOT NULL,
    CONSTRAINT pk_dim_fecha PRIMARY KEY (fecha_key)
);

CREATE TABLE gold.dim_canal (
    canal_key  INT IDENTITY(1,1) NOT NULL,
    canal      VARCHAR(12)       NOT NULL,
    CONSTRAINT pk_dim_canal PRIMARY KEY (canal_key),
    CONSTRAINT uq_dim_canal UNIQUE (canal)
);

CREATE TABLE gold.dim_categoria (
    categoria_key  INT IDENTITY(1,1) NOT NULL,
    categoria      NVARCHAR(30)      NOT NULL,
    CONSTRAINT pk_dim_categoria PRIMARY KEY (categoria_key),
    CONSTRAINT uq_dim_categoria UNIQUE (categoria)
);

CREATE TABLE gold.dim_cliente (
    cliente_key       INT IDENTITY(1,1) NOT NULL,
    id_cliente        VARCHAR(11)       NOT NULL,   -- incluye el miembro 'DESCONOCIDO' (11 caracteres) para pedidos huérfanos
    id_cliente_maestro VARCHAR(11)      NOT NULL,
    nombre            NVARCHAR(120)     NULL,
    ciudad            NVARCHAR(40)      NULL,
    canal_registro    VARCHAR(12)       NULL,
    fecha_registro    DATE              NULL,
    cohorte_registro  DATE              NULL,
    CONSTRAINT pk_dim_cliente PRIMARY KEY (cliente_key),
    CONSTRAINT uq_dim_cliente UNIQUE (id_cliente)
);

CREATE TABLE gold.fact_pedido (            -- grano: un pedido
    id_pedido          VARCHAR(11)   NOT NULL,
    cliente_key        INT           NOT NULL,
    fecha_key          INT           NOT NULL,  -- según fecha_pedido
    canal_key          INT           NOT NULL,
    categoria_key      INT           NOT NULL,
    valor_bruto        DECIMAL(18,0) NOT NULL,
    descuento          DECIMAL(18,0) NOT NULL,
    venta_neta         DECIMAL(18,0) NOT NULL,  -- valor neto si ENTREGADO; 0 en los demás estados
    estado             VARCHAR(10)   NOT NULL,
    cuenta_como_venta  BIT           NOT NULL,
    fecha_entrega      DATE          NULL,
    CONSTRAINT pk_fact_pedido PRIMARY KEY (id_pedido),
    CONSTRAINT fk_fp_cliente   FOREIGN KEY (cliente_key)   REFERENCES gold.dim_cliente (cliente_key),
    CONSTRAINT fk_fp_fecha     FOREIGN KEY (fecha_key)     REFERENCES gold.dim_fecha (fecha_key),
    CONSTRAINT fk_fp_canal     FOREIGN KEY (canal_key)     REFERENCES gold.dim_canal (canal_key),
    CONSTRAINT fk_fp_categoria FOREIGN KEY (categoria_key) REFERENCES gold.dim_categoria (categoria_key)
);
CREATE INDEX ix_fp_fecha_canal ON gold.fact_pedido (fecha_key, canal_key) INCLUDE (venta_neta);
CREATE INDEX ix_fp_cliente     ON gold.fact_pedido (cliente_key);

CREATE TABLE gold.fact_pago (               -- grano: un pago o reembolso
    id_pago       VARCHAR(11)   NOT NULL,
    id_pedido     VARCHAR(11)   NOT NULL,
    fecha_key     INT           NOT NULL,
    medio_pago    NVARCHAR(20)  NOT NULL,
    valor         DECIMAL(18,0) NOT NULL,
    es_reembolso  BIT           NOT NULL,
    CONSTRAINT pk_fact_pago PRIMARY KEY (id_pago),
    CONSTRAINT fk_fpg_pedido FOREIGN KEY (id_pedido) REFERENCES gold.fact_pedido (id_pedido),
    CONSTRAINT fk_fpg_fecha  FOREIGN KEY (fecha_key) REFERENCES gold.dim_fecha (fecha_key)
);

CREATE TABLE gold.fact_ticket (             -- grano: un ticket
    id_ticket           VARCHAR(10)   NOT NULL,
    cliente_key         INT           NOT NULL,
    id_pedido           VARCHAR(11)   NULL,     -- sin FK: 32 tickets son de pedidos en cuarentena
    fecha_creacion_key  INT           NOT NULL,
    canal_soporte       NVARCHAR(10)  NULL,
    estado              VARCHAR(10)   NULL,
    tipo_caso           NVARCHAR(40)  NULL,
    horas_resolucion    DECIMAL(10,1) NULL,     -- nulo si el cierre es inválido o el ticket está abierto
    CONSTRAINT pk_fact_ticket PRIMARY KEY (id_ticket),
    CONSTRAINT fk_ft_cliente FOREIGN KEY (cliente_key)        REFERENCES gold.dim_cliente (cliente_key),
    CONSTRAINT fk_ft_fecha   FOREIGN KEY (fecha_creacion_key) REFERENCES gold.dim_fecha (fecha_key)
);

-- Tabla de salida exigida por la prueba. Grano: día x canal x categoría.
CREATE TABLE gold.fact_venta_neta_diaria (
    fecha_key      INT           NOT NULL,
    canal_key      INT           NOT NULL,
    categoria_key  INT           NOT NULL,
    num_pedidos    INT           NOT NULL,
    venta_bruta    DECIMAL(18,0) NOT NULL,
    descuento      DECIMAL(18,0) NOT NULL,
    venta_neta     DECIMAL(18,0) NOT NULL,
    CONSTRAINT pk_fact_vnd PRIMARY KEY (fecha_key, canal_key, categoria_key),
    CONSTRAINT fk_vnd_fecha     FOREIGN KEY (fecha_key)     REFERENCES gold.dim_fecha (fecha_key),
    CONSTRAINT fk_vnd_canal     FOREIGN KEY (canal_key)     REFERENCES gold.dim_canal (canal_key),
    CONSTRAINT fk_vnd_categoria FOREIGN KEY (categoria_key) REFERENCES gold.dim_categoria (categoria_key)
);
GO
