"""Hora actual del sistema (zona horaria de la universidad). Centralizada para poder simularla en pruebas."""
from datetime import datetime

from . import config


def ahora() -> datetime:
    """Fecha y hora local sin zona (las reservas guardan fecha y hora locales)."""
    return datetime.now(config.ZONA).replace(tzinfo=None, microsecond=0)
