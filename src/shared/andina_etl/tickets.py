"""Soporte opcional: conservar fechas incoherentes marcadas, sin SLA inventado."""
import pandas as pd
from .contracts import COLS_TICKETS
from .rules import _a_fecha, _texto, _cuarentena, hash_filas


def validar_tickets(raw):
    df = raw.copy()
    h = hash_filas(raw, COLS_TICKETS)
    ids = _texto(df['id_ticket'])
    creada = _a_fecha(df['fecha_creacion'])
    cerrada = _a_fecha(df['fecha_cierre'])
    reglas = {'ID_TICKET_NULO': ids.isna(),
              'ID_TICKET_DUPLICADO': ids.notna() & ids.duplicated(keep=False),
              'FECHA_CREACION_INVALIDA': creada.isna()}
    q = _cuarentena(raw, 'tickets_soporte', 'id_ticket', h, reglas)
    ok = ~pd.concat(reglas, axis=1).any(axis=1)
    estado = _texto(df['estado']).str.upper()
    invalido = cerrada.notna() & (cerrada < creada)
    sin_fecha = estado.eq('CERRADO') & cerrada.isna()
    horas = (cerrada-creada).dt.total_seconds()/3600
    out = pd.DataFrame(dict(id_ticket=ids, id_cliente=_texto(df['id_cliente']),
        id_pedido=_texto(df['id_pedido']), fecha_creacion=creada, canal_soporte=_texto(df['canal']),
        estado=estado, fecha_cierre=cerrada, descripcion_original=df['descripcion'],
        flag_cierre_invalido=invalido, flag_cerrado_sin_fecha=sin_fecha,
        horas_resolucion=horas.where(estado.eq('CERRADO') & ~invalido & ~sin_fecha), row_hash=h))
    return out[ok].reset_index(drop=True), q


ESQUEMA = '''CREATE TABLE IF NOT EXISTS silver_tickets (
id_ticket VARCHAR PRIMARY KEY, id_cliente VARCHAR, id_pedido VARCHAR,
fecha_creacion TIMESTAMP, canal_soporte VARCHAR, estado VARCHAR, fecha_cierre TIMESTAMP,
descripcion_original VARCHAR, flag_cierre_invalido BOOLEAN, flag_cerrado_sin_fecha BOOLEAN,
horas_resolucion DOUBLE, row_hash VARCHAR, ingested_at TIMESTAMP DEFAULT current_timestamp);
CREATE TABLE IF NOT EXISTS ticket_clasificacion (
id_ticket VARCHAR, texto_hash VARCHAR, version VARCHAR, tipo VARCHAR,
validado_humano BOOLEAN DEFAULT FALSE, PRIMARY KEY(id_ticket,texto_hash,version));'''
