"""Exclusión local, compuertas y estado operativo sin servicios externos."""
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@contextmanager
def bloqueo(db_path):
    """Un escritor por archivo. Un lock abandonado exige diagnóstico manual."""
    path = Path(str(Path(db_path).resolve()) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as e:
        raise RuntimeError('Corrida bloqueada: existe un lock; verificar proceso antes de retirarlo') from e
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'pid': os.getpid(), 'inicio_utc': datetime.now(timezone.utc).isoformat()}, f)
        yield
    finally:
        path.unlink(missing_ok=True)


@dataclass(frozen=True)
class PoliticaPublicacion:
    """Sin umbrales inventados por defecto; configurar tras acordarlos con negocio."""
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


def validar_publicacion(con, resumen, politica=None):
    politica = politica or PoliticaPublicacion()
    n, venta, fecha = con.execute("SELECT count(*), coalesce(sum(CASE WHEN estado='ENTREGADO' "
                                 "THEN valor_neto ELSE 0 END),0), max(fecha_pedido_dia) "
                                 "FROM silver_pedidos").fetchone()
    gold = con.execute('SELECT coalesce(sum(venta_neta),0) FROM gold_venta_neta_diaria').fetchone()[0]
    errores = []
    diferencias = con.execute("""WITH esperado AS (
        SELECT fecha_pedido_dia fecha,canal,categoria,count(*) num_pedidos,
        sum(valor_bruto) venta_bruta,sum(descuento) descuento,sum(valor_neto) venta_neta
        FROM silver_pedidos WHERE estado='ENTREGADO' GROUP BY 1,2,3
    ), diferencias AS (
        (SELECT * FROM esperado EXCEPT ALL SELECT * FROM gold_venta_neta_diaria)
        UNION ALL
        (SELECT * FROM gold_venta_neta_diaria EXCEPT ALL SELECT * FROM esperado)
    ) SELECT count(*) FROM diferencias""").fetchone()[0]
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


def actualizar_incidencias(con, tabla, raw, q, run_id):
    """Solo resuelve IDs reevaluados, nunca filas ausentes/fuera del watermark."""
    con.execute('''CREATE TABLE IF NOT EXISTS calidad_incidencias (
        tabla VARCHAR, id_registro VARCHAR, regla VARCHAR, estado VARCHAR,
        primera_observacion TIMESTAMP, ultima_revision TIMESTAMP, run_id VARCHAR,
        motivo VARCHAR, PRIMARY KEY(tabla,id_registro,regla))''')
    col_id = {'clientes':'id_cliente', 'pedidos':'id_pedido', 'pagos':'id_pago',
              'tickets_soporte':'id_ticket'}[tabla]
    ids = raw[[col_id]].rename(columns={col_id:'id_registro'}).fillna('')
    ids['id_registro'] = ids['id_registro'].astype(str).str.strip()
    con.register('ids_revisados', ids)
    con.execute("UPDATE calidad_incidencias SET estado='RESUELTA', ultima_revision=current_timestamp, "
                "run_id=?, motivo='No incumple en la última reevaluación' WHERE tabla=? "
                "AND id_registro IN (SELECT id_registro FROM ids_revisados)", [run_id, tabla])
    con.unregister('ids_revisados')
    for row in q[['id_registro','regla_violada']].drop_duplicates().itertuples(index=False):
        con.execute('''INSERT INTO calidad_incidencias VALUES (?,?,?,'ABIERTA',current_timestamp,
            current_timestamp,?,'Regla incumplida') ON CONFLICT(tabla,id_registro,regla)
            DO UPDATE SET estado='ABIERTA', ultima_revision=excluded.ultima_revision,
            run_id=excluded.run_id, motivo=excluded.motivo''',
            [tabla, str(row.id_registro).strip(), row.regla_violada, run_id])
