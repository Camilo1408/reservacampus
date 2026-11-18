"""Hora actual del sistema (zona horaria de la universidad). Centralizada para poder simularla en pruebas.

APP_RELOJ_INICIO (opcional, solo demos/pruebas): fecha-hora ISO desde la que "arranca" el reloj, p. ej.
2026-11-18T10:15. El tiempo sigue corriendo desde ahí. En producción no se define y se usa la hora real.
"""
import os
from datetime import datetime

from . import config

_INICIO_SIMULADO = os.getenv("APP_RELOJ_INICIO", "").strip()
_BASE = datetime.fromisoformat(_INICIO_SIMULADO) if _INICIO_SIMULADO else None
_ARRANQUE = datetime.now()


def ahora() -> datetime:
    """Fecha y hora local sin zona (las reservas guardan fecha y hora locales)."""
    if _BASE:
        return (_BASE + (datetime.now() - _ARRANQUE)).replace(microsecond=0)
    return datetime.now(config.ZONA).replace(tzinfo=None, microsecond=0)
