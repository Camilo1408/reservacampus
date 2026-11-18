"""Programador de tareas por tiempo sobre las reservas del día.

Línea de tiempo de una reserva (minutos respecto al inicio):
  -10  recordatorio por correo: "tu reserva empieza en 10 min; confirma tu llegada al llegar"
    0  aviso: "tu reserva empezó, confirma que estás en el espacio"
  +10  aviso: "no has confirmado; tienes 10 min antes de ser sancionado"
  +20  sin confirmación -> la reserva pasa a 'inasistencia' y se aplica sanción escalonada

Es idempotente (banderas en la reserva) y puede ejecutarse cada minuto (hilo interno) o desde un cron
externo (POST /tareas/ejecutar). Si el servicio estuvo dormido, los avisos vencidos se omiten pero las
inasistencias se procesan igual al despertar.
"""
import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, reloj, sanciones
from .database import SessionLocal
from .eventos import publicador
from .models import Reserva

log = logging.getLogger("reservas.tareas")
M = lambda n: timedelta(minutes=n)  # noqa: E731


def evento(r: Reserva, **extra) -> dict:
    return {"reserva_id": r.id, "usuario_id": r.usuario_id, "usuario_email": r.usuario_email,
            "usuario_nombre": r.usuario_nombre, "espacio": r.espacio.nombre, "fecha": r.fecha.isoformat(),
            "hora_inicio": r.hora_inicio.strftime("%H:%M"), "hora_fin": r.hora_fin.strftime("%H:%M"),
            "enlace": f"{config.FRONTEND_URL}/?confirmar={r.id}", **extra}


def procesar(db: Session, ahora: datetime | None = None) -> dict:
    ahora = ahora or reloj.ahora()
    res = {"recordatorios": 0, "avisos_inicio": 0, "avisos_finales": 0, "inasistencias": 0}
    pendientes = db.scalars(select(Reserva).where(
        Reserva.estado == "confirmada", Reserva.llegada_confirmada_en.is_(None),
        Reserva.fecha >= ahora.date() - timedelta(days=1), Reserva.fecha <= ahora.date())).all()
    for r in pendientes:
        ini = r.inicio_dt
        if ahora >= ini + M(config.LIMITE_CONFIRMACION):
            r.estado = "inasistencia"
            db.commit()
            sanciones.aplicar(db, usuario_id=r.usuario_id, email=r.usuario_email, nombre=r.usuario_nombre,
                              tipo="inasistencia", reserva_id=r.id, ahora=ahora,
                              motivo=f"No confirmaste tu llegada a {r.espacio.nombre} el {r.fecha:%d/%m} "
                                     f"a las {r.hora_inicio:%H:%M} dentro de los {config.LIMITE_CONFIRMACION} minutos.")
            publicador.publicar("reserva.inasistencia", evento(r))
            res["inasistencias"] += 1
        elif ahora >= ini + M(config.AVISO_SIN_CONFIRMAR):
            if not r.aviso_final:
                r.aviso_final = True
                db.commit()
                limite = (ini + M(config.LIMITE_CONFIRMACION)).strftime("%H:%M")
                publicador.publicar("reserva.aviso_inasistencia", evento(r, limite=limite))
                res["avisos_finales"] += 1
        elif ahora >= ini:
            if not r.aviso_inicio:
                r.aviso_inicio = True
                db.commit()
                publicador.publicar("reserva.confirmar_llegada", evento(r))
                res["avisos_inicio"] += 1
        elif ahora >= ini - M(config.RECORDATORIO_ANTES):
            if not r.aviso_previo:
                r.aviso_previo = True
                db.commit()
                publicador.publicar("reserva.recordatorio", evento(r))
                res["recordatorios"] += 1
    return res


class Programador(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="programador-tareas")
        self.detener = threading.Event()
        self.ultima: dict | None = None
        self.ultima_hora: datetime | None = None

    def ejecutar(self) -> dict:
        with SessionLocal() as db:
            self.ultima = procesar(db)
            self.ultima_hora = reloj.ahora()
        return self.ultima

    def run(self):
        while not self.detener.wait(config.TAREAS_INTERVALO_SEG):
            try:
                self.ejecutar()
            except Exception:
                log.exception("Fallo en el programador de tareas")
