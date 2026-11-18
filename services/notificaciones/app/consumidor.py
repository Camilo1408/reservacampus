"""Consumidor de eventos de reservas (Redis Streams + grupo de consumidores)."""
import json
from collections import defaultdict
import logging
import smtplib
import socket
import threading
import time
import html
from email.message import EmailMessage

import httpx
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .database import SessionLocal
from .models import Notificacion

log = logging.getLogger("notificaciones.consumidor")

# tipo -> (título, mensaje, texto del botón si el evento trae "enlace")
PLANTILLAS = {
    "reserva.creada": ("Reserva confirmada ✅",
                       "Tu reserva de {espacio} para el {fecha} de {hora_inicio} a {hora_fin} quedó confirmada. "
                       "Recuerda confirmar tu llegada en la app cuando estés en el espacio.", None),
    "reserva.cancelada": ("Reserva cancelada",
                          "La reserva de {espacio} del {fecha} ({hora_inicio}-{hora_fin}) fue cancelada.", None),
    "reserva.revocada": ("Tu reserva fue revocada ⚠️",
                         "La administración revocó tu reserva de {espacio} del {fecha} ({hora_inicio}-{hora_fin}). "
                         "Motivo: {justificacion}", None),
    "reserva.recordatorio": ("Tu reserva empieza en 10 minutos ⏰",
                             "Tu reserva de {espacio} empieza hoy a las {hora_inicio}. Al llegar, confirma tu "
                             "asistencia en la app; tienes hasta 20 minutos después del inicio.", "Confirmar llegada"),
    "reserva.confirmar_llegada": ("Confirma que estás en el espacio 📍",
                                  "Tu reserva de {espacio} ({hora_inicio}-{hora_fin}) ya empezó. Confirma tu llegada "
                                  "para conservarla.", "Confirmar llegada"),
    "reserva.aviso_inasistencia": ("Último aviso: confirma tu llegada ⚠️",
                                   "Aún no confirmas tu llegada a {espacio}. Si no lo haces antes de las {limite}, la "
                                   "reserva se marcará como inasistencia y recibirás una sanción.", "Confirmar llegada"),
    "reserva.inasistencia": ("Reserva marcada como inasistencia",
                             "No confirmaste tu llegada a {espacio} del {fecha} ({hora_inicio}-{hora_fin}).", None),
    "reporte.registrado": ("Recibimos tu reporte",
                           "Registramos que {espacio} no fue entregado a tiempo para tu reserva de las {hora_inicio}. "
                           "Tu llegada quedó confirmada. Si persiste el problema, contacta a soporte.", None),
    "sancion.aplicada": ("Recibiste una sanción (nivel {nivel})",
                         "Motivo: {motivo} {descripcion} Vigente hasta {hasta}.", None),
    "sancion.levantada": ("Tu sanción fue levantada ✅",
                          "La administración levantó tu sanción: {nota}. Ya puedes volver a reservar.", None),
    "usuario.password_reset": ("Restablece tu contraseña 🔑",
                               "Recibimos una solicitud para restablecer tu contraseña. El enlace vence en {minutos} "
                               "minutos. Si no fuiste tú, ignora este mensaje.", "Crear nueva contraseña"),
    "usuario.password_cambiada": ("Tu contraseña cambió",
                                  "La contraseña de tu cuenta se actualizó. Si no fuiste tú, contacta a soporte.", None),
    "usuario.estado_cambiado": ("Cambio en el estado de tu cuenta",
                                "Tu cuenta ahora está: {estado}. Motivo: {motivo}", None),
    "alerta.admin": ("{asunto}", "{mensaje}", None),
}


def html_correo(nombre: str, titulo: str, mensaje: str, enlace: str | None = None, boton: str | None = None) -> str:
    esc = lambda t: html.escape(str(t))  # noqa: E731
    accion = (f'<p style="margin:22px 0"><a href="{esc(enlace)}" style="background:#3b4cca;color:#fff;'
              f'text-decoration:none;padding:12px 20px;border-radius:10px;font-weight:bold;display:inline-block">'
              f'{esc(boton)}</a></p>') if enlace and boton and enlace.startswith(("http://", "https://")) else ""
    return f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;border:1px solid #e2e6f0;
    border-radius:12px;overflow:hidden"><div style="background:#3b4cca;color:#fff;padding:16px 20px;font-size:18px">
    <b>ReservaCampus</b></div><div style="padding:20px;color:#15192b;line-height:1.5"><p>Hola {esc(nombre)},</p>
    <h3 style="margin:0 0 8px">{esc(titulo)}</h3><p>{esc(mensaje)}</p>{accion}
    <p style="color:#5d6480;font-size:13px">Este es un mensaje automático de la plataforma de reservas.</p></div></div>"""


def enviar_por_brevo(destino: str, nombre: str, asunto: str, cuerpo_html: str) -> bool:
    """API HTTP de Brevo (Render gratuito bloquea los puertos SMTP)."""
    r = httpx.post("https://api.brevo.com/v3/smtp/email", timeout=15,
                   headers={"api-key": config.BREVO_API_KEY, "accept": "application/json"},
                   json={"sender": {"name": config.MAIL_FROM_NAME, "email": config.MAIL_FROM},
                         "to": [{"email": destino, "name": nombre or destino}],
                         "subject": asunto, "htmlContent": cuerpo_html})
    if r.status_code >= 300:
        log.warning("Brevo respondió %s: %s", r.status_code, r.text[:200])
        return False
    return True


def enviar_por_smtp(destino: str, asunto: str, cuerpo_html: str) -> bool:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, destino, asunto
    msg.set_content("Abre este correo en un cliente compatible con HTML.")
    msg.add_alternative(cuerpo_html, subtype="html")
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
        s.starttls()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.send_message(msg)
    return True


def enviar_correo(destino: str, nombre: str, asunto: str, mensaje: str, enlace: str | None = None,
                  boton: str | None = None) -> bool:
    cuerpo = html_correo(nombre, asunto, mensaje, enlace, boton)
    try:
        if config.BREVO_API_KEY and config.MAIL_FROM:
            return enviar_por_brevo(destino, nombre, asunto, cuerpo)
        if config.SMTP_HOST:
            return enviar_por_smtp(destino, asunto, cuerpo)
    except Exception as e:  # el correo es "best effort": no debe tumbar el consumidor
        log.warning("No se pudo enviar correo a %s: %s", destino, e)
    return False


def procesar_evento(db: Session, evento_id: str, tipo: str, datos: dict) -> Notificacion | None:
    """Crea la notificación de un evento. Idempotente: si el evento ya se procesó, no lo duplica."""
    if tipo not in PLANTILLAS:
        return None
    if db.scalar(select(Notificacion).where(Notificacion.evento_id == evento_id)):
        return None
    t_titulo, t_mensaje, boton = PLANTILLAS[tipo]
    valores = defaultdict(str, datos)
    titulo, mensaje = t_titulo.format_map(valores)[:120], t_mensaje.format_map(valores)[:500]
    n = Notificacion(usuario_id=int(datos["usuario_id"]), email=datos["usuario_email"], tipo=tipo,
                     titulo=titulo, mensaje=mensaje, evento_id=evento_id)
    n.correo_enviado = enviar_correo(n.email, datos.get("usuario_nombre", ""), titulo, mensaje,
                                     datos.get("enlace"), boton)
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
