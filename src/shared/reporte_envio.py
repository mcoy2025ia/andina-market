"""IA-R05: transporte del reporte diario, con reintentos y sin envíos duplicados.

Este módulo **no envía nada por sí solo**. Para que salga un correo tienen que darse
tres cosas a la vez: destinatarios declarados, `autorizado=True` escrito a propósito
por quien tiene la autorización (U07), y un transporte real inyectado. El valor por
defecto escribe a disco. Así el camino fácil nunca es el que manda correo.

Qué resuelve, y por qué cada decisión:

- **Duplicados.** La identidad del reporte es el hash de su contenido, no la fecha ni
  la hora. Reejecutar el proceso el mismo día, o reintentar tras una caída, no vuelve
  a enviar lo mismo: el registro de envíos lo reconoce y lo omite. Si el dato cambió,
  el contenido cambia, la identidad cambia y sí se envía: es un reporte distinto.
- **Reintentos.** Solo ante fallos declarados transitorios. Un rechazo del servidor
  (buzón inexistente, credencial inválida) no se reintenta: repetirlo no lo arregla y
  consume la ventana de entrega.
- **Un fallo no se anota como enviado.** Queda como FALLIDO y la siguiente corrida
  vuelve a intentarlo. Lo contrario perdería el reporte en silencio.
- **Sin secretos.** La configuración guarda el *nombre* de la variable de entorno con
  la credencial, nunca su valor, y el registro de envíos tampoco lo toca.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from andina_etl.operations import bloqueo
from reporte_archivo import preparar

REGISTRO = 'envios.json'


class ErrorTransporteTemporal(RuntimeError):
    """Fallo del que tiene sentido reintentar: red, tiempo de espera, 4xx/5xx pasajeros."""


class ErrorTransportePermanente(RuntimeError):
    """Fallo que un reintento no arregla: destinatario inválido, credencial rechazada."""


class EnvioNoAutorizado(RuntimeError):
    pass


@dataclass(frozen=True)
class Destino:
    """Configuración del envío. Nunca contiene la credencial, solo dónde buscarla."""
    destinatarios: tuple[str, ...] = ()
    remitente: str = ''
    asunto: str = 'Venta neta diaria · Andina Market'
    servidor: str | None = None
    puerto: int = 587
    variable_credencial: str = 'REPORTE_SMTP_PASSWORD'
    usuario: str = ''
    autorizado: bool = False

    def exigir_autorizacion(self) -> None:
        if not self.autorizado:
            raise EnvioNoAutorizado(
                'El envío no está autorizado: falta la decisión de U07 '
                '(destinatarios, canal y horario). La vista previa local sí está disponible.')
        if not self.destinatarios:
            raise EnvioNoAutorizado('No hay destinatarios declarados')
        if not self.remitente:
            raise EnvioNoAutorizado('No hay remitente declarado')

    def describir(self) -> dict:
        """Lo que se puede registrar y mostrar: nunca la credencial."""
        return {'destinatarios': list(self.destinatarios), 'remitente': self.remitente,
                'servidor': self.servidor, 'puerto': self.puerto,
                'credencial_en': self.variable_credencial, 'autorizado': self.autorizado}


# --------------------------------------------------------------- transportes

@dataclass
class TransporteBandeja:
    """Transporte por defecto: deja el documento en una carpeta. No usa la red."""
    carpeta: Path
    enviados: list = field(default_factory=list)

    def enviar(self, identidad: str, documento: str, destino: Destino) -> str:
        carpeta = Path(self.carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f'{identidad}.html'
        temporal = ruta.with_suffix('.tmp')
        try:
            temporal.write_text(documento, encoding='utf-8')
            os.replace(temporal, ruta)
        finally:
            temporal.unlink(missing_ok=True)
        self.enviados.append(identidad)
        return f'bandeja:{ruta.name}'


class TransporteSMTP:
    """Envío real por SMTP. **No ejecutado**: su validación es E02/U07.

    La credencial se lee del entorno en el momento del envío y no se guarda en
    ningún atributo, para que no acabe en un volcado de estado ni en el registro.
    """

    def __init__(self, tiempo_espera: float = 30.0):
        self.tiempo_espera = tiempo_espera

    def enviar(self, identidad: str, documento: str, destino: Destino) -> str:
        import smtplib
        from email.message import EmailMessage

        clave = os.environ.get(destino.variable_credencial)
        if not clave:
            raise ErrorTransportePermanente(
                f'Falta la credencial en {destino.variable_credencial}')
        mensaje = EmailMessage()
        mensaje['Subject'] = destino.asunto
        mensaje['From'] = destino.remitente
        mensaje['To'] = ', '.join(destino.destinatarios)
        # Identidad del contenido en la cabecera: permite al servidor y al buzón
        # reconocer un reenvío del mismo reporte.
        mensaje['Message-ID'] = f'<{identidad}@andina-market>'
        mensaje.set_content('Este reporte requiere un cliente con HTML.')
        mensaje.add_alternative(documento, subtype='html')
        try:
            with smtplib.SMTP(destino.servidor, destino.puerto,
                              timeout=self.tiempo_espera) as servidor:
                servidor.starttls()
                servidor.login(destino.usuario or destino.remitente, clave)
                servidor.send_message(mensaje)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused,
                smtplib.SMTPSenderRefused) as e:
            raise ErrorTransportePermanente(type(e).__name__) from e
        except (smtplib.SMTPException, OSError) as e:
            raise ErrorTransporteTemporal(type(e).__name__) from e
        return identidad


# ------------------------------------------------------------------ registro

def _leer_registro(carpeta: Path) -> dict:
    ruta = Path(carpeta) / REGISTRO
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        # Un registro ilegible no puede interpretarse como «no se envió nada»:
        # eso duplicaría envíos. Se detiene y se pide revisión.
        raise RuntimeError(f'Registro de envíos ilegible: {ruta}')


def _escribir_registro(carpeta: Path, datos: dict) -> None:
    ruta = Path(carpeta) / REGISTRO
    temporal = ruta.with_suffix('.tmp')
    try:
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


def historial(carpeta) -> dict:
    return _leer_registro(Path(carpeta))


# ----------------------------------------------------------------- despacho

def despachar(db, dia, carpeta, destino: Destino, transporte=None, *,
              reintentos: int = 2, dormir=time.sleep) -> dict:
    """Prepara el reporte del día y lo entrega una sola vez.

    Devuelve siempre un diccionario con el estado; solo lanza excepción cuando el
    problema es de configuración (sin autorización) o deja el sistema en un estado
    que nadie debería interpretar solo (registro ilegible).
    """
    if reintentos < 0:
        raise ValueError('Los reintentos no pueden ser negativos')
    destino.exigir_autorizacion()
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    identidad, documento, contenido = preparar(db, dia)
    transporte = transporte or TransporteBandeja(carpeta)

    with bloqueo(carpeta / 'despacho'):
        registro = _leer_registro(carpeta)
        previo = registro.get(identidad)
        if previo and previo.get('estado') == 'ENVIADO':
            # Mismo contenido ya entregado: no se vuelve a enviar.
            return {'id': identidad, 'estado': 'DUPLICADO_OMITIDO', 'intentos': 0,
                    'enviado_en': previo.get('enviado_en'), 'fecha': contenido['fecha'],
                    'referencia': previo.get('referencia')}

        intentos, referencia, error = 0, None, None
        for intento in range(1, reintentos + 2):
            intentos = intento
            try:
                referencia = transporte.enviar(identidad, documento, destino)
            except ErrorTransportePermanente as e:
                error = f'PERMANENTE: {e}'
                break                       # reintentar no lo arregla
            except ErrorTransporteTemporal as e:
                error = f'TEMPORAL: {e}'
                if intento <= reintentos:
                    dormir(min(0.5 * 2 ** (intento - 1), 8))
                    continue
                break
            else:
                error = None
                break

        resultado = {
            'id': identidad, 'fecha': contenido['fecha'],
            'estado': 'ENVIADO' if error is None else 'FALLIDO',
            'intentos': intentos, 'referencia': referencia, 'error': error,
            'enviado_en': datetime.now().isoformat(timespec='seconds') if error is None else None,
            'destino': destino.describir(),
        }
        # El fallo también se anota: así queda rastro de que se intentó, pero sin
        # marcarlo como enviado, de modo que la siguiente corrida lo reintente.
        registro[identidad] = {k: v for k, v in resultado.items() if k != 'destino'}
        registro[identidad]['destino'] = destino.describir()
        registro[identidad]['ultimo_intento'] = datetime.now().isoformat(timespec='seconds')
        _escribir_registro(carpeta, registro)
    return resultado
