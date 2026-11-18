"""Sanciones escalonadas por mal uso de espacios (no entregar a tiempo o no confirmar llegada).

Reincidencia: cada infracción válida (ocupación o inasistencia) sube un nivel, incluso si una sanción
anterior ya se cumplió o fue levantada. Solo las sanciones ANULADAS (p. ej. un reporte falso) no cuentan.
"""
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .eventos import publicador
from .models import Sancion

DESCRIPCION = {
    1: "No puedes hacer reservas durante el día siguiente.",
    2: "No puedes hacer reservas durante los próximos 3 días.",
    3: "No puedes hacer reservas durante la próxima semana.",
    4: "Tu cuenta quedó suspendida para reservar hasta que un administrador la reactive.",
}


def calcular_hasta(nivel: int, ahora: datetime) -> datetime | None:
    if nivel == 1:
        return datetime.combine(ahora.date() + timedelta(days=2), time(0))  # fin del día siguiente
    if nivel == 2:
        return ahora + timedelta(days=3)
    if nivel == 3:
        return ahora + timedelta(days=7)
    return None


def nivel_siguiente(db: Session, usuario_id: int) -> int:
    previas = db.scalar(select(func.count(Sancion.id)).where(
        Sancion.usuario_id == usuario_id, Sancion.tipo.in_(["ocupacion", "inasistencia"]),
        Sancion.estado != "anulada"))
    return min(previas + 1, 4)


def sancion_activa(db: Session, usuario_id: int, ahora: datetime) -> Sancion | None:
    candidatas = db.scalars(select(Sancion).where(Sancion.usuario_id == usuario_id, Sancion.estado == "vigente")
                            .order_by(Sancion.id.desc())).all()
    activas = [s for s in candidatas if s.activa(ahora)]
    # la más restrictiva: indefinida primero, luego la que termina más tarde
    return max(activas, key=lambda s: (s.hasta is None, s.hasta or ahora), default=None)


def evento_sancion(s: Sancion) -> dict:
    return {"sancion_id": s.id, "usuario_id": s.usuario_id, "usuario_email": s.usuario_email,
            "usuario_nombre": s.usuario_nombre, "nivel": s.nivel, "tipo": s.tipo, "motivo": s.motivo,
            "descripcion": DESCRIPCION.get(s.nivel) if s.tipo != "manual" else
            ("No puedes hacer reservas " + (f"hasta el {s.hasta:%d/%m/%Y a las %H:%M}." if s.hasta
                                             else "hasta que un administrador levante la sanción.")),
            "hasta": s.hasta.strftime("%d/%m/%Y %H:%M") if s.hasta else "que un administrador la levante"}


def aplicar(db: Session, *, usuario_id: int, email: str, nombre: str, tipo: str, motivo: str, ahora: datetime,
            reserva_id: int | None = None, nivel: int | None = None, dias: int | None = None,
            creada_por: str = "sistema") -> Sancion:
    """Crea la sanción (nivel automático por reincidencia salvo que se indique) y notifica al usuario."""
    if tipo == "manual":
        nivel = nivel or 0
        hasta = None if dias is None else ahora + timedelta(days=dias)
    else:
        nivel = nivel or nivel_siguiente(db, usuario_id)
        hasta = calcular_hasta(nivel, ahora)
    s = Sancion(usuario_id=usuario_id, usuario_email=email, usuario_nombre=nombre, nivel=nivel, tipo=tipo,
                motivo=motivo, reserva_id=reserva_id, desde=ahora, hasta=hasta, creada_por=creada_por)
    db.add(s)
    db.commit()
    db.refresh(s)
    publicador.publicar("sancion.aplicada", evento_sancion(s))
    return s
