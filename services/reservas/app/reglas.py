"""Reglas de negocio puras (sin BD) para validar una reserva. Fáciles de probar unitariamente."""
from datetime import date, datetime, time, timedelta

from . import config


class ReglaVioladaError(ValueError):
    pass


def minutos(t: time) -> int:
    return t.hour * 60 + t.minute


def se_solapan(a_ini: time, a_fin: time, b_ini: time, b_fin: time) -> bool:
    return a_ini < b_fin and a_fin > b_ini


def validar_horario(fecha: date, inicio: time, fin: time, apertura: time, cierre: time,
                    ahora: datetime | None = None) -> None:
    ahora = ahora or datetime.now(config.ZONA)
    hoy = ahora.date()
    if inicio >= fin:
        raise ReglaVioladaError("La hora de fin debe ser posterior a la de inicio")
    if inicio.minute % 30 or fin.minute % 30 or inicio.second or fin.second:
        raise ReglaVioladaError("Las reservas se hacen en bloques de 30 minutos (ej. 10:00, 10:30)")
    duracion = minutos(fin) - minutos(inicio)
    if duracion < config.DURACION_MIN:
        raise ReglaVioladaError(f"La duración mínima es {config.DURACION_MIN} minutos")
    if duracion > config.DURACION_MAX:
        raise ReglaVioladaError(f"La duración máxima es {config.DURACION_MAX // 60} horas")
    if inicio < apertura or fin > cierre:
        raise ReglaVioladaError(f"El espacio atiende de {apertura:%H:%M} a {cierre:%H:%M}")
    if fecha < hoy or (fecha == hoy and inicio <= ahora.time().replace(tzinfo=None)):
        raise ReglaVioladaError("No se puede reservar en el pasado")
    if fecha > hoy + timedelta(days=config.DIAS_ANTICIPACION):
        raise ReglaVioladaError(f"Solo se puede reservar con máximo {config.DIAS_ANTICIPACION} días de anticipación")


def validar_capacidad(asistentes: int, capacidad: int) -> None:
    if asistentes > capacidad:
        raise ReglaVioladaError(f"El espacio tiene capacidad para {capacidad} personas")
