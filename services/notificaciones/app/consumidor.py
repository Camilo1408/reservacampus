"""Consumidor de eventos de reservas (Redis Streams + grupo de consumidores)."""
import json
import logging
import smtplib
import socket
import threading
import time
from email.message import EmailMessage

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .database import SessionLocal
from .models import Notificacion

log = logging.getLogger("notificaciones.consumidor")

PLANTILLAS = {
    "reserva.creada": ("Reserva confirmada ✅",
                       "Tu reserva de {espacio} para el {fecha} de {hora_inicio} a {hora_fin} quedó confirmada."),
    "reserva.cancelada": ("Reserva cancelada",
                          "La reserva de {espacio} del {fecha} ({hora_inicio}-{hora_fin}) fue cancelada."),
}


def enviar_correo(destino: str, asunto: str, cuerpo: str) -> bool:
    if not config.SMTP_HOST:
        return False
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, destino, asunto
        msg.set_content(cuerpo)
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:  # el correo es "best effort": no debe tumbar el consumidor
        log.warning("No se pudo enviar correo a %s: %s", destino, e)
        return False


def procesar_evento(db: Session, evento_id: str, tipo: str, datos: dict) -> Notificacion | None:
    """Crea la notificación de un evento. Idempotente: si el evento ya se procesó, no lo duplica."""
    if tipo not in PLANTILLAS:
        return None
    if db.scalar(select(Notificacion).where(Notificacion.evento_id == evento_id)):
        return None
    titulo, plantilla = PLANTILLAS[tipo]
    mensaje = plantilla.format(**datos)
    n = Notificacion(usuario_id=int(datos["usuario_id"]), email=datos["usuario_email"], tipo=tipo,
                     titulo=titulo, mensaje=mensaje, evento_id=evento_id)
    n.correo_enviado = enviar_correo(n.email, titulo, f"Hola {datos.get('usuario_nombre', '')},\n\n{mensaje}")
    db.add(n)
    db.commit()
    return n


class Consumidor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="consumidor-eventos")
        self.nombre = f"{socket.gethostname()}"
        self.procesados = 0
        self.conectado = False
        self.detener = threading.Event()

    def _asegurar_grupo(self, r: redis.Redis):
        try:
            r.xgroup_create(config.STREAM_EVENTOS, config.GRUPO, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def _manejar(self, r: redis.Redis, mensajes):
        for _, entradas in mensajes or []:
            for evento_id, campos in entradas:
                eid = evento_id.decode() if isinstance(evento_id, bytes) else evento_id
                c = {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                     for k, v in campos.items()}
                try:
                    with SessionLocal() as db:
                        procesar_evento(db, eid, c["tipo"], json.loads(c["datos"]))
                    r.xack(config.STREAM_EVENTOS, config.GRUPO, eid)
                    self.procesados += 1
                except Exception:
                    log.exception("Error procesando evento %s (quedará pendiente)", eid)

    def run(self):
        if not config.REDIS_URL:
            log.warning("REDIS_URL no configurado: el consumidor no se inicia")
            return
        while not self.detener.is_set():
            try:
                r = redis.Redis.from_url(config.REDIS_URL, socket_timeout=10)
                self._asegurar_grupo(r)
                self.conectado = True
                # 1) Reprocesar pendientes (eventos leídos pero no confirmados antes de una caída)
                self._manejar(r, r.xreadgroup(config.GRUPO, self.nombre, {config.STREAM_EVENTOS: "0"}, count=50))
                # 2) Escuchar eventos nuevos
                while not self.detener.is_set():
                    msgs = r.xreadgroup(config.GRUPO, self.nombre, {config.STREAM_EVENTOS: ">"}, count=10, block=5000)
                    self._manejar(r, msgs)
            except redis.RedisError as e:
                self.conectado = False
                log.warning("Redis no disponible (%s). Reintentando en 5 s", e)
                time.sleep(5)
