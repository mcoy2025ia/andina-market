"""IA-R02: las extensiones locales (soporte, estrella, contratos, incidencias y
publicación consistente) escritas para el flujo Delta de Fabric o Databricks.

Por qué este archivo existe aparte de `rules_spark.py`: aquél son reglas de fila,
funciones puras de DataFrame. Esto es orquestación sobre tablas, y en Delta no hay
transacción entre tablas como en DuckDB. La diferencia obliga a un diseño distinto,
no a una traducción literal:

- **Publicación consistente sin transacción.** Local envuelve toda la corrida en una
  transacción DuckDB: si algo falla, no queda nada a medias. Delta solo garantiza
  atomicidad por tabla. Aquí la consistencia se consigue al revés: los hechos se
  escriben con el `run_id` de la corrida, se concilia contra Silver y solo si
  cuadra se mueve el puntero `publicacion_actual`. Los consumidores leen las vistas
  `v_fact_*`, que filtran por el run publicado, así que nunca ven una carga a medias
  ni una que no pasó las compuertas.
- **Separación por testabilidad.** Las sentencias que no dependen de Delta
  (`INSERT INTO`, `INSERT OVERWRITE`, `SELECT`) se devuelven como texto y se prueban
  contra Spark local comparando con el resultado de DuckDB. Las que sí dependen de
  Delta (`MERGE`, `UPDATE`, `DELETE`) viven en funciones con el prefijo `delta_` y
  **no se han ejecutado**: su validación es E04.

Las claves sustitutas usan el mismo criterio de orden que la versión DuckDB
(`ORDER BY` sobre el valor natural), de modo que ambos motores asignan las mismas
claves sobre los mismos datos y la comparación fila a fila es exacta.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from rules_spark import _cuarentena, _txt, hash_cols

COLS_TICKETS = ['id_ticket', 'id_cliente', 'id_pedido', 'fecha_creacion', 'canal',
                'estado', 'fecha_cierre', 'descripcion']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']


# --------------------------------------------------------------------- soporte

def _fecha_ticket(nombre: str):
    """ISO con o sin hora, igual que `pandas.to_datetime(format='ISO8601')`."""
    return F.coalesce(F.expr(f"try_to_timestamp({nombre}, 'yyyy-MM-dd HH:mm:ss')"),
                      F.expr(f"try_to_timestamp({nombre}, 'yyyy-MM-dd')"))


def hash_texto_normalizado(nombre: str):
    """Espejo exacto de `andina_etl.etiquetas.hash_texto`.

    Mismo orden de operaciones que la versión pandas (traducir acentos, minúsculas,
    colapsar espacios) y el mismo juego de caracteres: si divergieran, las etiquetas
    revisadas dejarían de casar con los tickets en uno de los dos motores.
    """
    sin_acentos = F.translate(F.col(nombre), 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')
    return F.sha2(F.trim(F.regexp_replace(F.lower(sin_acentos), r'\s+', ' ')), 256)


def validar_tickets(raw: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Espejo de `andina_etl.tickets.validar_tickets`.

    Las fechas incoherentes no se descartan: el ticket se conserva con su bandera y
    sin horas de resolución, para no inventar un SLA que la fuente no respalda.
    """
    df = (raw.withColumn('row_hash', hash_cols(COLS_TICKETS))
          .withColumn('x_id', _txt('id_ticket'))
          .withColumn('x_creada', _fecha_ticket('fecha_creacion'))
          .withColumn('x_cerrada', _fecha_ticket('fecha_cierre')))
    df = df.withColumn('x_veces', F.count(F.lit(1)).over(Window.partitionBy('x_id')))
    reglas = {
        'ID_TICKET_NULO': F.col('x_id').isNull(),
        # El id repetido manda todas las copias a cuarentena: no se sabe cuál vale.
        'ID_TICKET_DUPLICADO': F.col('x_id').isNotNull() & (F.col('x_veces') > 1),
        'FECHA_CREACION_INVALIDA': F.col('x_creada').isNull(),
    }
    cuarentena = _cuarentena(df, 'tickets_soporte', COLS_TICKETS, reglas)
    malo = (F.coalesce(reglas['ID_TICKET_NULO'], F.lit(False))
            | F.coalesce(reglas['ID_TICKET_DUPLICADO'], F.lit(False))
            | F.coalesce(reglas['FECHA_CREACION_INVALIDA'], F.lit(False)))

    estado = F.upper(_txt('estado'))
    invalido = F.col('x_cerrada').isNotNull() & (F.col('x_cerrada') < F.col('x_creada'))
    sin_fecha = (estado == 'CERRADO') & F.col('x_cerrada').isNull()
    horas = (F.col('x_cerrada').cast('double') - F.col('x_creada').cast('double')) / 3600
    out = df.filter(~malo).select(
        F.col('x_id').alias('id_ticket'),
        _txt('id_cliente').alias('id_cliente'),
        _txt('id_pedido').alias('id_pedido'),
        F.col('x_creada').alias('fecha_creacion'),
        _txt('canal').alias('canal_soporte'),
        estado.alias('estado'),
        F.col('x_cerrada').alias('fecha_cierre'),
        F.col('descripcion').alias('descripcion_original'),
        hash_texto_normalizado('descripcion').alias('texto_hash'),
        F.coalesce(invalido, F.lit(False)).alias('flag_cierre_invalido'),
        F.coalesce(sin_fecha, F.lit(False)).alias('flag_cerrado_sin_fecha'),
        F.when((estado == 'CERRADO') & ~F.coalesce(invalido, F.lit(False))
               & ~F.coalesce(sin_fecha, F.lit(False)), horas).alias('horas_resolucion'),
        F.col('row_hash'),
    )
    return out, cuarentena


# ------------------------------------------------------------ DDL de extensión

DDL_EXTENSIONES = {
    'silver_tickets': """id_ticket STRING, id_cliente STRING, id_pedido STRING,
        fecha_creacion TIMESTAMP, canal_soporte STRING, estado STRING, fecha_cierre TIMESTAMP,
        descripcion_original STRING, texto_hash STRING, flag_cierre_invalido BOOLEAN,
        flag_cerrado_sin_fecha BOOLEAN, horas_resolucion DOUBLE, row_hash STRING,
        ingested_at TIMESTAMP""",
    'calidad_incidencias': """tabla STRING, id_registro STRING, regla STRING, estado STRING,
        primera_observacion TIMESTAMP, ultima_revision TIMESTAMP, run_id STRING, motivo STRING""",
    # tipo + estado + origen: la propuesta de un clasificador y la decisión de una
    # persona se guardan por separado, nunca en la misma columna.
    'ticket_clasificacion': """texto_hash STRING, version STRING, tipo STRING, estado STRING,
        origen STRING, anotadores STRING, motivo STRING, particion STRING, confianza DOUBLE,
        importado_en TIMESTAMP""",
    'publicacion_actual': """id INT, run_id STRING, validado_en TIMESTAMP, venta_neta BIGINT""",
    'gold_dim_fecha': """fecha_key INT, fecha DATE, anio SMALLINT, trimestre SMALLINT, mes SMALLINT,
        nombre_mes STRING, anio_mes STRING, dia_semana SMALLINT, es_fin_de_semana BOOLEAN""",
    'gold_dim_canal': 'canal_key INT, canal STRING',
    'gold_dim_categoria': 'categoria_key INT, categoria STRING',
    'gold_dim_cliente': """cliente_key INT, id_cliente STRING, id_cliente_maestro STRING,
        nombre STRING, ciudad STRING, canal_registro STRING, fecha_registro DATE,
        cohorte_registro DATE""",
    'gold_fact_pedido': """id_pedido STRING, cliente_key INT, fecha_key INT, canal_key INT,
        categoria_key INT, valor_bruto BIGINT, descuento BIGINT, venta_neta BIGINT, estado STRING,
        cuenta_como_venta BOOLEAN, fecha_entrega DATE, run_id STRING""",
    'gold_fact_pago': """id_pago STRING, id_pedido STRING, fecha_key INT, medio_pago STRING,
        valor BIGINT, es_reembolso BOOLEAN, run_id STRING""",
    'gold_fact_venta_neta_diaria': """fecha_key INT, canal_key INT, categoria_key INT,
        num_pedidos INT, venta_bruta BIGINT, descuento BIGINT, venta_neta BIGINT, run_id STRING""",
    'gold_fact_ticket': """id_ticket STRING, cliente_key INT, id_pedido STRING,
        fecha_creacion_key INT, canal_soporte STRING, estado STRING, tipo_caso STRING,
        tipo_caso_propuesto STRING, clasificacion_estado STRING, clasificacion_version STRING,
        horas_resolucion DOUBLE, run_id STRING""",
}

FACTS = ('gold_fact_pedido', 'gold_fact_pago', 'gold_fact_venta_neta_diaria', 'gold_fact_ticket')


# ------------------------------------------------------------- modelo estrella

@dataclass(frozen=True)
class Paso:
    """Un paso del modelo estrella: qué tabla, cómo se escribe y el SELECT que la calcula.

    El SELECT va separado de la escritura a propósito. Así la parte que decide los
    valores —la que tiene que dar exactamente lo mismo que DuckDB— se puede ejecutar
    y comparar sin tablas Delta ni permisos de escritura, y la parte que persiste se
    reduce a una línea por paso.
    """
    tabla: str
    modo: str           # 'anexar' (altas que no mueven claves) | 'reemplazar' (hechos)
    select: str


def sentencia(paso: Paso, T) -> str:
    """SQL de escritura del paso. `INSERT OVERWRITE` es atómico por tabla en Delta."""
    destino = T(paso.tabla)
    verbo = 'INSERT INTO' if paso.modo == 'anexar' else 'INSERT OVERWRITE TABLE'
    return f'{verbo} {destino} {paso.select}'


def _limpiar(sql: str) -> str:
    return ' '.join(sql.split())


def pasos_dimensiones(T, desde: date, hasta: date) -> list[Paso]:
    """Altas de dimensión, solo para valores nuevos: las claves ya emitidas no se mueven.

    `desde`/`hasta` se expanden a años completos igual que la versión local, porque la
    medida DAX de período comparable necesita el calendario sin huecos.
    """
    inicio, fin = date(desde.year, 1, 1), date(hasta.year, 12, 31)
    pasos = []
    for nombre in ('canal', 'categoria'):
        pasos.append(Paso(f'gold_dim_{nombre}', 'anexar', _limpiar(f"""
            SELECT (SELECT coalesce(max({nombre}_key), 0) FROM {T(f'gold_dim_{nombre}')})
                   + row_number() OVER (ORDER BY p.{nombre}) AS {nombre}_key, p.{nombre}
            FROM (SELECT DISTINCT {nombre} FROM {T('silver_pedidos')}) p
            WHERE NOT EXISTS (SELECT 1 FROM {T(f'gold_dim_{nombre}')} d WHERE d.{nombre} = p.{nombre})
        """)))
    pasos.append(Paso('gold_dim_cliente', 'anexar', _limpiar(f"""
        SELECT 0 AS cliente_key, 'DESCONOCIDO' AS id_cliente, 'DESCONOCIDO' AS id_cliente_maestro,
               CAST(NULL AS STRING) AS nombre, CAST(NULL AS STRING) AS ciudad,
               CAST(NULL AS STRING) AS canal_registro, CAST(NULL AS DATE) AS fecha_registro,
               CAST(NULL AS DATE) AS cohorte_registro
        WHERE NOT EXISTS (SELECT 1 FROM {T('gold_dim_cliente')} WHERE cliente_key = 0)
    """)))
    pasos.append(Paso('gold_dim_cliente', 'anexar', _limpiar(f"""
        SELECT (SELECT coalesce(max(cliente_key), 0) FROM {T('gold_dim_cliente')})
               + row_number() OVER (ORDER BY c.id_cliente) AS cliente_key,
               c.id_cliente, m.id_cliente_maestro, c.nombre, c.ciudad, c.canal_registro,
               c.fecha_registro, c.cohorte_registro
        FROM {T('silver_clientes')} c
        JOIN {T('v_cliente_maestro')} m ON m.id_cliente = c.id_cliente
        WHERE NOT EXISTS (SELECT 1 FROM {T('gold_dim_cliente')} d WHERE d.id_cliente = c.id_cliente)
    """)))
    meses = ', '.join(f"'{m}'" for m in MESES)
    pasos.append(Paso('gold_dim_fecha', 'anexar', _limpiar(f"""
        SELECT cast(date_format(g.d, 'yyyyMMdd') AS INT) AS fecha_key, g.d AS fecha,
               cast(year(g.d) AS SMALLINT) AS anio, cast(quarter(g.d) AS SMALLINT) AS trimestre,
               cast(month(g.d) AS SMALLINT) AS mes,
               element_at(array({meses}), month(g.d)) AS nombre_mes,
               date_format(g.d, 'yyyy-MM') AS anio_mes,
               cast(weekday(g.d) + 1 AS SMALLINT) AS dia_semana,
               weekday(g.d) + 1 >= 6 AS es_fin_de_semana
        FROM (SELECT explode(sequence(DATE'{inicio}', DATE'{fin}', interval 1 day)) AS d) g
        WHERE NOT EXISTS (SELECT 1 FROM {T('gold_dim_fecha')} f WHERE f.fecha = g.d)
    """)))
    return pasos


def sql_etiqueta_vigente(T) -> str:
    """Etiqueta vigente por texto: la última importada de cada estado, por separado.

    Espejo de la vista `v_etiqueta_vigente` de DuckDB. Mantener revisada y propuesta
    en columnas distintas es lo que impide que una propuesta se publique como validada.
    """
    return _limpiar(f"""
        WITH ordenadas AS (
            SELECT *, row_number() OVER (PARTITION BY texto_hash, estado
                                         ORDER BY importado_en DESC, version DESC) AS n
            FROM {T('ticket_clasificacion')}
        )
        SELECT texto_hash,
               max(CASE WHEN estado = 'REVISADA'  THEN tipo    END) AS tipo_revisado,
               max(CASE WHEN estado = 'REVISADA'  THEN version END) AS version_revisada,
               max(CASE WHEN estado = 'PROPUESTA' THEN tipo    END) AS tipo_propuesto,
               max(CASE WHEN estado = 'PROPUESTA' THEN version END) AS version_propuesta
        FROM ordenadas WHERE n = 1 GROUP BY texto_hash
    """)


def sql_cliente_maestro(T) -> str:
    """Mismo documento bajo dos ids es la misma persona. Vista, no columna: así refleja
    siempre el estado actual de Silver."""
    return _limpiar(f"""
        SELECT id_cliente,
               min(id_cliente) OVER (PARTITION BY coalesce(documento_limpio, id_cliente))
                   AS id_cliente_maestro
        FROM {T('silver_clientes')}
    """)


def pasos_hechos(T, run_id: str) -> list[Paso]:
    """Reconstrucción completa de los hechos, marcados con el run que los produjo.

    La reconstrucción completa prioriza auditabilidad para el tamaño del caso; no se
    presenta como carga incremental de hechos a escala.
    """
    return [
        Paso('gold_fact_pedido', 'reemplazar', _limpiar(f"""
            SELECT p.id_pedido,
                   CASE WHEN s.id_cliente IS NULL THEN 0 ELSE c.cliente_key END AS cliente_key,
                   f.fecha_key, can.canal_key, cat.categoria_key, p.valor_bruto, p.descuento,
                   CASE WHEN p.estado = 'ENTREGADO' THEN p.valor_neto ELSE 0 END AS venta_neta,
                   p.estado, p.estado = 'ENTREGADO' AS cuenta_como_venta, p.fecha_entrega,
                   '{run_id}' AS run_id
            FROM {T('silver_pedidos')} p
            LEFT JOIN {T('silver_clientes')} s ON s.id_cliente = p.id_cliente
            LEFT JOIN {T('gold_dim_cliente')} c ON c.id_cliente = s.id_cliente
            JOIN {T('gold_dim_fecha')} f ON f.fecha = p.fecha_pedido_dia
            JOIN {T('gold_dim_canal')} can ON can.canal = p.canal
            JOIN {T('gold_dim_categoria')} cat ON cat.categoria = p.categoria
        """)),
        Paso('gold_fact_pago', 'reemplazar', _limpiar(f"""
            SELECT g.id_pago, g.id_pedido, f.fecha_key, g.medio_pago, g.valor, g.es_reembolso,
                   '{run_id}' AS run_id
            FROM {T('silver_pagos')} g
            JOIN {T('gold_dim_fecha')} f ON f.fecha = g.fecha_pago
            JOIN {T('gold_fact_pedido')} o ON o.id_pedido = g.id_pedido
        """)),
        Paso('gold_fact_venta_neta_diaria', 'reemplazar', _limpiar(f"""
            SELECT f.fecha_key, c.canal_key, k.categoria_key, v.num_pedidos, v.venta_bruta,
                   v.descuento, v.venta_neta, '{run_id}' AS run_id
            FROM {T('gold_venta_neta_diaria')} v
            JOIN {T('gold_dim_fecha')} f ON f.fecha = v.fecha
            JOIN {T('gold_dim_canal')} c ON c.canal = v.canal
            JOIN {T('gold_dim_categoria')} k ON k.categoria = v.categoria
        """)),
        Paso('gold_fact_ticket', 'reemplazar', _limpiar(f"""
            SELECT t.id_ticket,
                   CASE WHEN s.id_cliente IS NULL THEN 0 ELSE c.cliente_key END AS cliente_key,
                   t.id_pedido, f.fecha_key AS fecha_creacion_key, t.canal_soporte, t.estado,
                   e.tipo_revisado AS tipo_caso, e.tipo_propuesto AS tipo_caso_propuesto,
                   CASE WHEN e.tipo_revisado IS NOT NULL THEN 'REVISADA'
                        WHEN e.tipo_propuesto IS NOT NULL THEN 'PROPUESTA' END
                        AS clasificacion_estado,
                   coalesce(e.version_revisada, e.version_propuesta) AS clasificacion_version,
                   t.horas_resolucion, '{run_id}' AS run_id
            FROM {T('silver_tickets')} t
            LEFT JOIN {T('silver_clientes')} s ON s.id_cliente = t.id_cliente
            LEFT JOIN {T('gold_dim_cliente')} c ON c.id_cliente = s.id_cliente
            LEFT JOIN {T('v_etiqueta_vigente')} e ON e.texto_hash = t.texto_hash
            JOIN {T('gold_dim_fecha')} f ON f.fecha = cast(t.fecha_creacion AS DATE)
        """)),
    ]


def comprobar_estrella(spark, T) -> dict:
    """La estrella no puede perder filas ni dejar de conciliar con el agregado diario.

    Es la misma comprobación que hace la versión local antes de confirmar la
    transacción; aquí corre antes de mover el puntero de publicación.
    """
    conteos = {}
    for fact, origen in [('gold_fact_pedido', 'silver_pedidos'), ('gold_fact_pago', 'silver_pagos'),
                         ('gold_fact_ticket', 'silver_tickets'),
                         ('gold_fact_venta_neta_diaria', 'gold_venta_neta_diaria')]:
        n = spark.sql(f'SELECT count(*) FROM {T(fact)}').first()[0]
        if n != spark.sql(f'SELECT count(*) FROM {T(origen)}').first()[0]:
            raise RuntimeError(f'Modelo estrella pierde filas: {fact}')
        conteos[fact] = n
    total, nulos = spark.sql(f"""SELECT coalesce(sum(venta_neta), 0),
        count(*) FILTER (WHERE cliente_key IS NULL) FROM {T('gold_fact_pedido')}""").first()
    diario = spark.sql(
        f"SELECT coalesce(sum(venta_neta), 0) FROM {T('gold_venta_neta_diaria')}").first()[0]
    if nulos or total != diario:
        raise RuntimeError('Modelo estrella no concilia')
    return conteos


def delta_refrescar_atributos_cliente(T) -> str:
    """Atributos descriptivos de `dim_cliente` al día, conservando la clave.

    Requiere Delta (`MERGE INTO`). **No ejecutado**: se valida en E04.
    """
    return ' '.join(f"""
        MERGE INTO {T('gold_dim_cliente')} d
        USING (SELECT c.id_cliente, m.id_cliente_maestro, c.nombre, c.ciudad, c.canal_registro,
                      c.fecha_registro, c.cohorte_registro
               FROM {T('silver_clientes')} c
               JOIN {T('v_cliente_maestro')} m ON m.id_cliente = c.id_cliente) s
        ON d.id_cliente = s.id_cliente
        WHEN MATCHED THEN UPDATE SET
            d.id_cliente_maestro = s.id_cliente_maestro, d.nombre = s.nombre, d.ciudad = s.ciudad,
            d.canal_registro = s.canal_registro, d.fecha_registro = s.fecha_registro,
            d.cohorte_registro = s.cohorte_registro
    """.split())


# ----------------------------------------------------- incidencias de calidad

def delta_sentencias_incidencias(T, tabla: str, run_id: str) -> list[str]:
    """Abre y resuelve incidencias sin borrar historia.

    Solo se resuelven los ids efectivamente reevaluados en esta corrida: la ausencia
    de una fila en el lote no es prueba de que el problema se corrigiera. Las vistas
    `ids_revisados` y `q_nueva` las registra el notebook antes de llamar.
    Requiere Delta (`MERGE INTO`). **No ejecutado**: se valida en E04.
    """
    return [' '.join(s.split()) for s in [f"""
        MERGE INTO {T('calidad_incidencias')} t
        USING (SELECT DISTINCT trim(id_registro) AS id_registro FROM ids_revisados) s
        ON t.tabla = '{tabla}' AND t.id_registro = s.id_registro
        WHEN MATCHED THEN UPDATE SET t.estado = 'RESUELTA', t.ultima_revision = current_timestamp(),
            t.run_id = '{run_id}', t.motivo = 'No incumple en la última reevaluación'
    """, f"""
        MERGE INTO {T('calidad_incidencias')} t
        USING (SELECT DISTINCT trim(id_registro) AS id_registro, regla_violada FROM q_nueva) s
        ON t.tabla = '{tabla}' AND t.id_registro = s.id_registro AND t.regla = s.regla_violada
        WHEN MATCHED THEN UPDATE SET t.estado = 'ABIERTA', t.ultima_revision = current_timestamp(),
            t.run_id = '{run_id}', t.motivo = 'Regla incumplida'
        WHEN NOT MATCHED THEN INSERT (tabla, id_registro, regla, estado, primera_observacion,
            ultima_revision, run_id, motivo)
        VALUES ('{tabla}', s.id_registro, s.regla_violada, 'ABIERTA', current_timestamp(),
            current_timestamp(), '{run_id}', 'Regla incumplida')
    """]]


# ------------------------------------------------------ publicación consistente

@dataclass(frozen=True)
class PoliticaPublicacion:
    """Sin umbrales inventados por defecto; configurar tras acordarlos con negocio (U08)."""
    max_fraccion_cuarentena: float | None = None
    min_pedidos: int | None = None
    venta_esperada: int | None = None
    tolerancia: int = 0
    fecha_minima_datos: date | None = None

    def __post_init__(self):
        if self.max_fraccion_cuarentena is not None and not 0 <= self.max_fraccion_cuarentena <= 1:
            raise ValueError('Fracción de cuarentena debe estar entre 0 y 1')
        if self.tolerancia < 0 or (self.min_pedidos is not None and self.min_pedidos < 0):
            raise ValueError('Tolerancia y mínimo no pueden ser negativos')


class PublicacionBloqueada(RuntimeError):
    pass


def sql_conciliacion(T) -> str:
    """Filas en las que Gold y Silver no dicen lo mismo, al mismo grano.

    `EXCEPT ALL` en los dos sentidos detecta tanto lo que falta en Gold como lo que
    sobra, que es justo el daño que deja una carga interrumpida entre tablas.
    """
    return ' '.join(f"""
        WITH esperado AS (
            SELECT fecha_pedido_dia AS fecha, canal, categoria, count(*) AS num_pedidos,
                   sum(valor_bruto) AS venta_bruta, sum(descuento) AS descuento,
                   sum(valor_neto) AS venta_neta
            FROM {T('silver_pedidos')} WHERE estado = 'ENTREGADO' GROUP BY 1, 2, 3
        ), publicado AS (
            SELECT fecha, canal, categoria, num_pedidos, venta_bruta, descuento, venta_neta
            FROM {T('gold_venta_neta_diaria')}
        ), diferencias AS (
            (SELECT * FROM esperado EXCEPT ALL SELECT * FROM publicado)
            UNION ALL
            (SELECT * FROM publicado EXCEPT ALL SELECT * FROM esperado)
        ) SELECT count(*) FROM diferencias
    """.split())


def validar_publicacion(spark, T, resumen: dict | None = None,
                        politica: PoliticaPublicacion | None = None) -> dict:
    """Compuertas antes de mover el puntero de publicación. Espejo de `operations.validar_publicacion`."""
    politica = politica or PoliticaPublicacion()
    resumen = resumen or {}
    n, venta, fecha = spark.sql(f"""
        SELECT count(*), coalesce(sum(CASE WHEN estado = 'ENTREGADO' THEN valor_neto ELSE 0 END), 0),
               max(fecha_pedido_dia) FROM {T('silver_pedidos')}""").first()
    gold = spark.sql(
        f"SELECT coalesce(sum(venta_neta), 0) FROM {T('gold_venta_neta_diaria')}").first()[0]
    diferencias = spark.sql(sql_conciliacion(T)).first()[0]

    errores = []
    if venta != gold or diferencias:
        errores.append('Silver y Gold no concilian')
    if politica.min_pedidos is not None and n < politica.min_pedidos:
        errores.append('Volumen menor que mínimo configurado')
    if politica.venta_esperada is not None and abs(venta - politica.venta_esperada) > politica.tolerancia:
        errores.append('Venta fuera de tolerancia configurada')
    if politica.fecha_minima_datos and (fecha is None or fecha < politica.fecha_minima_datos):
        errores.append('Frescura insuficiente')
    for tabla in ('clientes', 'pedidos', 'pagos', 'tickets_soporte'):
        x = resumen.get(tabla, {})
        if politica.max_fraccion_cuarentena is not None and x.get('leidos', 0):
            if x.get('rechazados_lote', 0) / x['leidos'] > politica.max_fraccion_cuarentena:
                errores.append(f'{tabla}: cuarentena supera umbral configurado')
    if errores:
        raise PublicacionBloqueada('; '.join(errores))
    return {'estado': 'VALIDADO', 'pedidos': n, 'venta_neta': int(venta),
            'fecha_maxima': fecha.isoformat() if fecha else None,
            'politica': 'configurada' if politica != PoliticaPublicacion() else 'conciliacion_basica'}


def sentencias_vistas_publicadas(T, temporal: bool = False) -> list[str]:
    """Vistas de consumo: solo el run publicado.

    Es lo que sustituye a la transacción de DuckDB. Mientras `publicacion_actual` no
    apunte al run nuevo, Power BI y el reporte siguen viendo el anterior completo,
    aunque las tablas de hechos ya tengan filas a medio escribir.

    `temporal` existe solo para las pruebas: ahí las tablas son vistas temporales, y
    Spark no deja que una vista persistente referencie una temporal. El cuerpo de la
    consulta es el mismo en los dos casos.
    """
    clase = 'TEMP VIEW' if temporal else 'VIEW'
    return [' '.join(f"""
        CREATE OR REPLACE {clase} {T('v_' + fact.replace('gold_', ''))} AS
        SELECT * FROM {T(fact)}
        WHERE run_id = (SELECT run_id FROM {T('publicacion_actual')} WHERE id = 1)
    """.split()) for fact in FACTS]


def delta_publicar(T, run_id: str, venta_neta: int) -> str:
    """Movimiento del puntero de publicación: una sola escritura, atómica en Delta.

    Requiere Delta (`MERGE INTO`). **No ejecutado**: se valida en E04.
    """
    return ' '.join(f"""
        MERGE INTO {T('publicacion_actual')} t
        USING (SELECT 1 AS id, '{run_id}' AS run_id, current_timestamp() AS validado_en,
                      CAST({venta_neta} AS BIGINT) AS venta_neta) s
        ON t.id = s.id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """.split())


# ------------------------------------------------- contratos de archivo entrada

class ErrorContrato(ValueError):
    pass


CONTRATOS = {
    'clientes': ['id_cliente', 'nombre', 'documento', 'ciudad', 'canal_registro', 'fecha_registro'],
    'pedidos': ['id_pedido', 'id_cliente', 'fecha_pedido', 'canal', 'categoria',
                'valor_bruto', 'descuento', 'estado', 'fecha_entrega'],
    'pagos': ['id_pago', 'id_pedido', 'fecha_pago', 'valor', 'medio_pago', 'fecha_carga'],
    'tickets_soporte': COLS_TICKETS,
}


def verificar_contrato(spark, ruta: str, tabla: str) -> dict:
    """Contrato estructural del CSV antes de leerlo como datos.

    Un archivo inválido bloquea la corrida entera, no sus filas: si la cabecera
    cambió, lo que haya debajo no significa lo que el proceso cree.

    Diferencia declarada con la versión local: allí se valida la codificación byte a
    byte con el lector de Python. Aquí Spark sustituye los bytes inválidos por el
    carácter de reemplazo, así que esa comprobación se hace sobre su presencia, no
    sobre una excepción del decodificador.
    """
    esperadas = CONTRATOS[tabla]
    cabecera = (spark.read.option('header', False).option('encoding', 'UTF-8')
                .csv(ruta).limit(1).first())
    if cabecera is None:
        raise ErrorContrato(f'{tabla}: archivo sin cabecera')
    nombres = [(c or '').strip().lstrip('﻿') for c in cabecera]
    if not nombres or len(nombres) != len(set(nombres)):
        raise ErrorContrato(f'{tabla}: cabecera vacía o repetida')
    faltan = sorted(set(esperadas) - set(nombres))
    if faltan:
        raise ErrorContrato(f'{tabla}: faltan columnas {faltan}')

    esquema = ', '.join(f'`{c}` string' for c in nombres) + ', _corrupto string'
    df = (spark.read.option('header', True).option('mode', 'PERMISSIVE')
          .option('columnNameOfCorruptRecord', '_corrupto').option('encoding', 'UTF-8')
          .schema(esquema).csv(ruta)).cache()
    malformadas = df.filter(F.col('_corrupto').isNotNull()).count()
    if malformadas:
        raise ErrorContrato(f'{tabla}: {malformadas} registros con ancho inválido')
    sucias = df.filter(reduce_or([F.col(f'`{c}`').contains('�') for c in nombres])).count()
    if sucias:
        raise ErrorContrato(f'{tabla}: {sucias} registros con codificación inválida')
    filas = df.count()
    df.unpersist()
    return {'filas': filas, 'extras': sorted(set(nombres) - set(esperadas))}


def reduce_or(columnas):
    from functools import reduce
    return reduce(lambda a, b: a | b, columnas)
