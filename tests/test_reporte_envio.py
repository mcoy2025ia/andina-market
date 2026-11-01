"""IA-R05: pruebas de integración del transporte del reporte.

Se simulan los cuatro casos que pide el pendiente —éxito, fallo, reintento y
duplicado— con transportes falsos. Ninguna prueba abre una conexión: lo que se
verifica es la lógica de entrega, no el servidor de correo de nadie.
"""
from datetime import date

import pytest

from andina_etl.pipeline import ejecutar
from reporte_envio import (
    Destino, EnvioNoAutorizado, ErrorTransportePermanente, ErrorTransporteTemporal,
    TransporteBandeja, despachar, historial)
from .conftest import datos_base, escribir_csvs

DIA = date(2025, 1, 10)
AUTORIZADO = Destino(destinatarios=('finanzas@ejemplo.test',), remitente='etl@ejemplo.test',
                     autorizado=True)


@pytest.fixture
def caso(tmp_path):
    raw, db = tmp_path / 'raw', tmp_path / 'wh.duckdb'
    escribir_csvs(raw, datos_base())
    ejecutar(raw, db)
    return db, tmp_path / 'salida'


class TransporteFalso:
    """Transporte programable: se le dice qué hacer en cada intento."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.llamadas = []

    def enviar(self, identidad, documento, destino):
        self.llamadas.append({'id': identidad, 'destinatarios': destino.destinatarios,
                              'documento': documento})
        accion = self.guion.pop(0) if self.guion else 'ok'
        if isinstance(accion, Exception):
            raise accion
        return f'falso:{identidad[:8]}'


# ------------------------------------------------------------------- éxito

def test_envio_correcto_queda_registrado(caso):
    db, salida = caso
    transporte = TransporteFalso(['ok'])
    r = despachar(db, DIA, salida, AUTORIZADO, transporte)
    assert r['estado'] == 'ENVIADO' and r['intentos'] == 1 and r['error'] is None
    assert len(transporte.llamadas) == 1
    assert transporte.llamadas[0]['destinatarios'] == ('finanzas@ejemplo.test',)
    assert '90,000' in transporte.llamadas[0]['documento']
    registro = historial(salida)
    assert registro[r['id']]['estado'] == 'ENVIADO'
    assert registro[r['id']]['enviado_en']


# ---------------------------------------------------------------- duplicado

def test_el_mismo_reporte_no_se_envia_dos_veces(caso):
    db, salida = caso
    primero = TransporteFalso(['ok'])
    segundo = TransporteFalso(['ok'])
    a = despachar(db, DIA, salida, AUTORIZADO, primero)
    b = despachar(db, DIA, salida, AUTORIZADO, segundo)
    assert a['estado'] == 'ENVIADO'
    assert b['estado'] == 'DUPLICADO_OMITIDO' and b['id'] == a['id']
    assert segundo.llamadas == []              # no se tocó el transporte
    assert b['enviado_en'] == a['enviado_en']


def test_si_el_dato_cambia_el_reporte_es_otro_y_si_se_envia(caso, tmp_path):
    db, salida = caso
    transporte = TransporteFalso(['ok', 'ok'])
    a = despachar(db, DIA, salida, AUTORIZADO, transporte)
    # Otro día tiene otro contenido: identidad distinta, envío legítimo.
    b = despachar(db, date(2025, 2, 1), salida, AUTORIZADO, transporte)
    assert b['id'] != a['id'] and b['estado'] == 'ENVIADO'
    assert len(transporte.llamadas) == 2


# ----------------------------------------------------------------- reintento

def test_un_fallo_transitorio_se_reintenta_y_acaba_enviando(caso):
    db, salida = caso
    transporte = TransporteFalso([ErrorTransporteTemporal('timeout'),
                                  ErrorTransporteTemporal('503'), 'ok'])
    esperas = []
    r = despachar(db, DIA, salida, AUTORIZADO, transporte,
                  reintentos=2, dormir=esperas.append)
    assert r['estado'] == 'ENVIADO' and r['intentos'] == 3
    assert len(transporte.llamadas) == 3
    assert esperas == [0.5, 1.0]               # espera creciente entre intentos


def test_se_agotan_los_reintentos_y_queda_fallido_para_la_proxima(caso):
    db, salida = caso
    transporte = TransporteFalso([ErrorTransporteTemporal('t')] * 5)
    r = despachar(db, DIA, salida, AUTORIZADO, transporte, reintentos=2, dormir=lambda _: None)
    assert r['estado'] == 'FALLIDO' and r['intentos'] == 3
    assert r['error'].startswith('TEMPORAL')
    assert historial(salida)[r['id']]['estado'] == 'FALLIDO'

    # No quedó marcado como enviado, así que la siguiente corrida reintenta.
    reintento = TransporteFalso(['ok'])
    segundo = despachar(db, DIA, salida, AUTORIZADO, reintento)
    assert segundo['estado'] == 'ENVIADO' and len(reintento.llamadas) == 1


# -------------------------------------------------------------------- fallo

def test_un_fallo_permanente_no_se_reintenta(caso):
    db, salida = caso
    transporte = TransporteFalso([ErrorTransportePermanente('buzón inexistente'),
                                  'ok', 'ok', 'ok'])
    r = despachar(db, DIA, salida, AUTORIZADO, transporte, reintentos=3, dormir=lambda _: None)
    assert r['estado'] == 'FALLIDO' and r['intentos'] == 1
    assert len(transporte.llamadas) == 1       # repetirlo no lo arreglaría
    assert r['error'].startswith('PERMANENTE')


# ------------------------------------------------------------- autorización

@pytest.mark.parametrize('destino,mensaje', [
    (Destino(destinatarios=('a@b.test',), remitente='c@d.test'), 'no está autorizado'),
    (Destino(remitente='c@d.test', autorizado=True), 'destinatarios'),
    (Destino(destinatarios=('a@b.test',), autorizado=True), 'remitente'),
])
def test_sin_autorizacion_o_sin_destinatarios_no_se_despacha(caso, destino, mensaje):
    db, salida = caso
    transporte = TransporteFalso(['ok'])
    with pytest.raises(EnvioNoAutorizado, match=mensaje):
        despachar(db, DIA, salida, destino, transporte)
    assert transporte.llamadas == []


# --------------------------------------------------------------- sin secretos

def test_el_registro_no_guarda_la_credencial(caso, monkeypatch):
    db, salida = caso
    monkeypatch.setenv('REPORTE_SMTP_PASSWORD', 'clave-secreta-no-debe-aparecer')
    destino = Destino(destinatarios=('a@b.test',), remitente='c@d.test',
                      servidor='smtp.ejemplo.test', autorizado=True)
    r = despachar(db, DIA, salida, destino, TransporteFalso(['ok']))
    texto = (salida / 'envios.json').read_text(encoding='utf-8')
    assert 'clave-secreta-no-debe-aparecer' not in texto
    assert 'REPORTE_SMTP_PASSWORD' in texto          # sí queda dónde buscarla
    assert r['destino']['credencial_en'] == 'REPORTE_SMTP_PASSWORD'
    assert 'clave' not in str(r['destino'])


def test_la_descripcion_del_destino_no_expone_la_clave():
    d = Destino(destinatarios=('a@b.test',), remitente='c@d.test', autorizado=True)
    assert set(d.describir()) == {'destinatarios', 'remitente', 'servidor', 'puerto',
                                  'credencial_en', 'autorizado'}


# ----------------------------------------------------- transporte por defecto

def test_el_transporte_por_defecto_escribe_a_disco_y_no_usa_red(caso):
    db, salida = caso
    r = despachar(db, DIA, salida, AUTORIZADO)
    assert r['estado'] == 'ENVIADO' and r['referencia'].startswith('bandeja:')
    assert (salida / f"{r['id']}.html").exists()


def test_una_bandeja_escribe_el_documento_completo(tmp_path):
    t = TransporteBandeja(tmp_path)
    ref = t.enviar('abc123', '<html>contenido</html>', AUTORIZADO)
    assert ref == 'bandeja:abc123.html'
    assert (tmp_path / 'abc123.html').read_text(encoding='utf-8') == '<html>contenido</html>'


def test_un_registro_corrupto_detiene_el_despacho(caso):
    db, salida = caso
    salida.mkdir(parents=True, exist_ok=True)
    (salida / 'envios.json').write_text('{ esto no es json', encoding='utf-8')
    with pytest.raises(RuntimeError, match='ilegible'):
        despachar(db, DIA, salida, AUTORIZADO, TransporteFalso(['ok']))
