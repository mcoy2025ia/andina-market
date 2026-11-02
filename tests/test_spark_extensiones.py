"""IA-R02: las extensiones locales llevadas a Spark dan el mismo resultado que DuckDB.

Qué se prueba aquí de verdad: las reglas de soporte, el modelo estrella completo
(dimensiones con sus claves y los cuatro hechos), la conciliación Silver↔Gold y las
compuertas de publicación. Todo contra el almacén DuckDB, fila a fila.

Qué NO se prueba, y por qué: las sentencias Delta (`MERGE`, `UPDATE`, `DELETE`,
`DESCRIBE HISTORY`) necesitan un runtime Delta. Aquí las tablas se sustituyen por
vistas temporales, que es lo que permite ejecutar el cálculo sin Delta ni permisos
de escritura. Lo que esas sentencias hacen se cierra en E04, no aquí.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from .conftest import motivo_para_omitir_spark

pyspark = pytest.importorskip('pyspark')
duckdb = pytest.importorskip('duckdb')
if motivo := motivo_para_omitir_spark():
    pytest.skip(motivo, allow_module_level=True)

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src' / 'shared' / 'spark'))
import extensiones_spark as ex  # noqa: E402

from andina_etl.pipeline import ejecutar  # noqa: E402
from andina_etl.tickets import validar_tickets as validar_tickets_pandas  # noqa: E402
from .conftest import COLS_TICKETS_PRUEBA, datos_base, escribir_csvs, tickets_base  # noqa: E402

# Columnas de Silver tal como las lee el modelo estrella (sin ingested_at).
ESQUEMAS = {
    'silver_clientes': ('id_cliente string, nombre string, documento_original string, '
                        'documento_limpio string, ciudad string, canal_registro string, '
                        'fecha_registro date, cohorte_registro date, row_hash string'),
    'silver_pedidos': ('id_pedido string, id_cliente string, fecha_pedido timestamp, '
                       'fecha_pedido_dia date, canal string, categoria string, valor_bruto bigint, '
                       'descuento bigint, valor_neto bigint, estado string, fecha_entrega date, '
                       'flag_cliente_desconocido boolean, hash_negocio string, row_hash string'),
    'silver_pagos': ('id_pago string, id_pedido string, fecha_pago date, valor bigint, '
                     'es_reembolso boolean, medio_pago string, fecha_carga date, '
                     'hash_negocio string, row_hash string'),
    'silver_tickets': ('id_ticket string, id_cliente string, id_pedido string, '
                       'fecha_creacion timestamp, canal_soporte string, estado string, '
                       'fecha_cierre timestamp, descripcion_original string, texto_hash string, '
                       'flag_cierre_invalido boolean, flag_cerrado_sin_fecha boolean, '
                       'horas_resolucion double, row_hash string'),
    'gold_venta_neta_diaria': ('fecha date, canal string, categoria string, num_pedidos int, '
                               'venta_bruta bigint, descuento bigint, venta_neta bigint'),
}


@pytest.fixture(scope='module')
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master('local[2]').appName('extensiones')
         .config('spark.sql.shuffle.partitions', '2').config('spark.ui.enabled', 'false')
         .config('spark.sql.ansi.enabled', 'true').getOrCreate())
    yield s
    s.stop()


class AlmacenVistas:
    """Sustituye las tablas Delta por vistas temporales.

    Cada paso se materializa (`collect` y vuelta a crear) antes de registrarlo: si no,
    Spark evaluaría perezosamente el `NOT EXISTS` del siguiente paso contra la propia
    vista que está construyendo.
    """

    def __init__(self, spark):
        self.spark = spark
        self.tablas = {}

    def T(self, nombre):
        return nombre

    def registrar(self, nombre, df):
        materializado = self.spark.createDataFrame(df.collect(), df.schema)
        self.tablas[nombre] = materializado
        materializado.createOrReplaceTempView(nombre)

    def vacia(self, nombre, esquema):
        self.registrar(nombre, self.spark.createDataFrame([], esquema))

    def aplicar(self, paso):
        nuevo = self.spark.sql(paso.select)
        if paso.modo == 'anexar' and paso.tabla in self.tablas:
            nuevo = self.tablas[paso.tabla].unionByName(nuevo)
        self.registrar(paso.tabla, nuevo)

    def filas(self, nombre, columnas):
        orden = ', '.join(columnas)
        return [tuple(r) for r in
                self.spark.sql(f'SELECT {orden} FROM {nombre} ORDER BY {orden}').collect()]


@pytest.fixture(scope='module')
def caso(tmp_path_factory):
    """Almacén DuckDB con los datos sintéticos, incluido soporte."""
    base = tmp_path_factory.mktemp('estrella')
    raw, db = base / 'raw', base / 'wh.duckdb'
    escribir_csvs(raw, datos_base())
    pd.DataFrame(tickets_base(), columns=COLS_TICKETS_PRUEBA).to_csv(
        raw / 'tickets_soporte.csv', index=False)
    ejecutar(raw, db)
    return db


def _cargar_silver(spark, almacen, db):
    with duckdb.connect(str(db), read_only=True) as con:
        for tabla, esquema in ESQUEMAS.items():
            columnas = [c.strip().split()[0] for c in esquema.split(',')]
            filas = con.execute(f"SELECT {', '.join(columnas)} FROM {tabla}").fetchall()
            almacen.registrar(tabla, spark.createDataFrame(filas, esquema))
    almacen.registrar('v_cliente_maestro', spark.sql(ex.sql_cliente_maestro(almacen.T)))
    almacen.vacia('ticket_clasificacion', ex.DDL_EXTENSIONES['ticket_clasificacion'])
    almacen.registrar('v_etiqueta_vigente', spark.sql(ex.sql_etiqueta_vigente(almacen.T)))


RUN = 'run-prueba'


def _construir_estrella(spark, db, run_id=RUN):
    almacen = AlmacenVistas(spark)
    _cargar_silver(spark, almacen, db)
    for nombre in ('gold_dim_canal', 'gold_dim_categoria', 'gold_dim_cliente', 'gold_dim_fecha'):
        almacen.vacia(nombre, ex.DDL_EXTENSIONES[nombre])
    for paso in ex.pasos_dimensiones(almacen.T, date(2025, 1, 1), date(2026, 9, 30)):
        almacen.aplicar(paso)
    for paso in ex.pasos_hechos(almacen.T, run_id):
        almacen.aplicar(paso)
    return almacen


@pytest.fixture(scope='module')
def estrella(spark, caso):
    """Se construye una sola vez: levantar Spark y materializar el calendario es caro.
    Las pruebas que alteran el almacén restauran lo que tocan."""
    return _construir_estrella(spark, caso)


@pytest.fixture
def estrella_aislada(spark, estrella):
    """Devuelve el almacén compartido y repone las tablas que la prueba modifique."""
    copia = dict(estrella.tablas)
    yield estrella
    for nombre, df in copia.items():
        if estrella.tablas.get(nombre) is not df:
            estrella.registrar(nombre, df)


# ------------------------------------------------------------------- soporte

def test_soporte_misma_cuarentena_y_mismos_validos(spark):
    filas = tickets_base()
    raw_pd = pd.DataFrame(filas, columns=COLS_TICKETS_PRUEBA, dtype=str)
    ok_pd, q_pd = validar_tickets_pandas(raw_pd)

    datos = (raw_pd.astype(object).where(raw_pd.notna(), None).values.tolist())
    raw_sp = spark.createDataFrame(datos, ', '.join(f'{c} string' for c in COLS_TICKETS_PRUEBA))
    ok_sp, q_sp = ex.validar_tickets(raw_sp)

    pares = lambda d: sorted((r['id_registro'], r['regla_violada']) for _, r in d.iterrows())  # noqa: E731
    q_sp_pd = pd.DataFrame([tuple(r) for r in q_sp.collect()], columns=q_sp.columns)
    assert pares(q_sp_pd) == pares(q_pd)

    a = pd.DataFrame([tuple(r) for r in ok_sp.collect()], columns=ok_sp.columns).set_index('id_ticket').sort_index()
    b = ok_pd.set_index('id_ticket').sort_index()
    assert list(a.index) == list(b.index)
    assert (a['estado'] == b['estado']).all()
    assert (a['row_hash'] == b['row_hash']).all()
    # El hash del texto es la clave por la que se asocian las etiquetas revisadas:
    # si los dos motores no lo calculan igual, la asociación se pierde en uno de ellos.
    assert (a['texto_hash'] == b['texto_hash']).all()
    assert (a['flag_cierre_invalido'] == b['flag_cierre_invalido']).all()
    assert (a['flag_cerrado_sin_fecha'] == b['flag_cerrado_sin_fecha']).all()
    # El SLA solo existe cuando la fuente lo respalda; en el resto es nulo en ambos motores.
    horas_a = a['horas_resolucion'].astype('float64').fillna(-1).tolist()
    horas_b = b['horas_resolucion'].astype('float64').fillna(-1).tolist()
    assert horas_a == horas_b


# ------------------------------------------------------------ modelo estrella

@pytest.mark.parametrize('dim,columnas', [
    ('dim_canal', ['canal_key', 'canal']),
    ('dim_categoria', ['categoria_key', 'categoria']),
    ('dim_cliente', ['cliente_key', 'id_cliente', 'id_cliente_maestro', 'ciudad']),
    ('dim_fecha', ['fecha_key', 'fecha', 'anio', 'trimestre', 'mes', 'nombre_mes',
                   'anio_mes', 'dia_semana', 'es_fin_de_semana']),
])
def test_dimensiones_identicas_a_duckdb(caso, estrella, dim, columnas):
    con_spark = estrella.filas(f'gold_{dim}', columnas)
    orden = ', '.join(columnas)
    with duckdb.connect(str(caso), read_only=True) as con:
        con_duck = [tuple(r) for r in
                    con.execute(f'SELECT {orden} FROM gold.{dim} ORDER BY {orden}').fetchall()]
    assert len(con_spark) == len(con_duck)
    assert [tuple(str(v) for v in f) for f in con_spark] == [tuple(str(v) for v in f) for f in con_duck]


@pytest.mark.parametrize('fact,columnas', [
    ('fact_pedido', ['id_pedido', 'cliente_key', 'fecha_key', 'canal_key', 'categoria_key',
                     'valor_bruto', 'descuento', 'venta_neta', 'estado', 'cuenta_como_venta']),
    ('fact_pago', ['id_pago', 'id_pedido', 'fecha_key', 'medio_pago', 'valor', 'es_reembolso']),
    ('fact_venta_neta_diaria', ['fecha_key', 'canal_key', 'categoria_key', 'num_pedidos',
                                'venta_bruta', 'descuento', 'venta_neta']),
    ('fact_ticket', ['id_ticket', 'cliente_key', 'fecha_creacion_key', 'canal_soporte', 'estado']),
])
def test_hechos_identicos_a_duckdb(caso, estrella, fact, columnas):
    con_spark = estrella.filas(f'gold_{fact}', columnas)
    orden = ', '.join(columnas)
    with duckdb.connect(str(caso), read_only=True) as con:
        con_duck = [tuple(r) for r in
                    con.execute(f'SELECT {orden} FROM gold.{fact} ORDER BY {orden}').fetchall()]
    assert [tuple(str(v) for v in f) for f in con_spark] == [tuple(str(v) for v in f) for f in con_duck]


def test_la_estrella_marca_el_run_y_concilia(spark, estrella):
    conteos = ex.comprobar_estrella(spark, estrella.T)
    assert conteos['gold_fact_pedido'] > 0
    runs = {r[0] for r in spark.sql('SELECT DISTINCT run_id FROM gold_fact_pedido').collect()}
    assert runs == {RUN}


def test_segunda_construccion_no_mueve_las_claves(estrella_aislada):
    """Una recarga no puede renumerar dimensiones: rompería cualquier informe guardado."""
    antes = {d: estrella_aislada.filas(f'gold_dim_{d}', [f'{d}_key', d])
             for d in ('canal', 'categoria')}
    clientes = estrella_aislada.filas('gold_dim_cliente', ['cliente_key', 'id_cliente'])
    # Segunda pasada sobre el mismo almacén, como una recarga.
    for paso in ex.pasos_dimensiones(estrella_aislada.T, date(2025, 1, 1), date(2026, 9, 30)):
        estrella_aislada.aplicar(paso)
    for d, esperado in antes.items():
        assert estrella_aislada.filas(f'gold_dim_{d}', [f'{d}_key', d]) == esperado
    assert estrella_aislada.filas('gold_dim_cliente', ['cliente_key', 'id_cliente']) == clientes


# ------------------------------------------------------ publicación consistente

def test_conciliacion_detecta_gold_alterado(spark, estrella_aislada):
    almacen = estrella_aislada
    assert spark.sql(ex.sql_conciliacion(almacen.T)).first()[0] == 0
    assert ex.validar_publicacion(spark, almacen.T)['estado'] == 'VALIDADO'

    # Una carga interrumpida entre tablas deja Gold con filas que Silver no respalda.
    alterado = spark.sql("""SELECT fecha, canal, categoria, num_pedidos, venta_bruta, descuento,
                            venta_neta + 1 AS venta_neta FROM gold_venta_neta_diaria""")
    almacen.registrar('gold_venta_neta_diaria', alterado)
    assert spark.sql(ex.sql_conciliacion(almacen.T)).first()[0] > 0
    with pytest.raises(ex.PublicacionBloqueada, match='concilian'):
        ex.validar_publicacion(spark, almacen.T)


@pytest.mark.parametrize('politica,mensaje', [
    (ex.PoliticaPublicacion(min_pedidos=999), 'Volumen'),
    (ex.PoliticaPublicacion(venta_esperada=1), 'tolerancia'),
    (ex.PoliticaPublicacion(fecha_minima_datos=date(2026, 9, 30)), 'Frescura'),
])
def test_compuertas_configuradas_bloquean(spark, estrella, politica, mensaje):
    with pytest.raises(ex.PublicacionBloqueada, match=mensaje):
        ex.validar_publicacion(spark, estrella.T, politica=politica)


def test_cuarentena_sobre_umbral_bloquea(spark, estrella):
    almacen = estrella
    resumen = {'pedidos': {'leidos': 100, 'rechazados_lote': 50}}
    with pytest.raises(ex.PublicacionBloqueada, match='cuarentena'):
        ex.validar_publicacion(spark, almacen.T, resumen,
                               ex.PoliticaPublicacion(max_fraccion_cuarentena=0.1))


def test_vistas_publicadas_filtran_por_el_run_publicado(spark, estrella_aislada):
    almacen = estrella_aislada
    almacen.registrar('publicacion_actual', spark.createDataFrame(
        [(1, 'run-anterior', None, 0)], ex.DDL_EXTENSIONES['publicacion_actual']))
    for sql in ex.sentencias_vistas_publicadas(almacen.T, temporal=True):
        spark.sql(sql)
    # Los hechos ya están escritos, pero el puntero aún apunta al run anterior:
    # el consumidor no ve nada de la carga a medio publicar.
    assert spark.sql('SELECT count(*) FROM v_fact_pedido').first()[0] == 0
    almacen.registrar('publicacion_actual', spark.createDataFrame(
        [(1, RUN, None, 0)], ex.DDL_EXTENSIONES['publicacion_actual']))
    assert spark.sql('SELECT count(*) FROM v_fact_pedido').first()[0] > 0


# --------------------------------------------------------- contrato de archivo

def test_contrato_rechaza_cabecera_y_ancho(spark, tmp_path):
    bueno = tmp_path / 'clientes.csv'
    escribir_csvs(tmp_path, {'clientes': datos_base()['clientes']})
    assert ex.verificar_contrato(spark, str(bueno), 'clientes')['filas'] == 3

    faltan = tmp_path / 'faltan.csv'
    faltan.write_text('id_cliente,nombre\nCL1,Ana\n', encoding='utf-8')
    with pytest.raises(ex.ErrorContrato, match='faltan columnas'):
        ex.verificar_contrato(spark, str(faltan), 'clientes')

    repetida = tmp_path / 'repetida.csv'
    repetida.write_text('id_cliente,id_cliente\na,b\n', encoding='utf-8')
    with pytest.raises(ex.ErrorContrato, match='repetida'):
        ex.verificar_contrato(spark, str(repetida), 'clientes')


def test_sentencia_de_escritura_usa_el_verbo_correcto():
    T = lambda n: f'andina.datos.{n}'  # noqa: E731
    anexar = ex.Paso('gold_dim_canal', 'anexar', 'SELECT 1, 2')
    reemplazar = ex.Paso('gold_fact_pedido', 'reemplazar', 'SELECT 1')
    assert ex.sentencia(anexar, T).startswith('INSERT INTO andina.datos.gold_dim_canal')
    assert ex.sentencia(reemplazar, T).startswith('INSERT OVERWRITE TABLE andina.datos.gold_fact_pedido')
