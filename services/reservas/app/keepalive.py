"""Mantiene vivo el servicio en Render (plan gratuito: se duerme tras 15 min sin tráfico).

Cada KEEPALIVE_MINUTOS (10 por defecto) hace GET a su propia URL pública /health, que entra por el proxy
de Render y cuenta como tráfico. Solo se activa si existe RENDER_EXTERNAL_URL (la define Render) o
KEEPALIVE_URL, y se puede apagar con KEEPALIVE=0. KEEPALIVE_HORAS="6-22" limita la franja (hora Colombia).
"""
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger("keepalive")
_iniciado = False


def _en_franja(franja: str) -> bool:
    try:
        ini, fin = (int(x) for x in franja.split("-"))
    except ValueError:
        return True
    hora = datetime.now(timezone(timedelta(hours=-5))).hour
    return ini <= hora < fin


def _bucle(url: str, minutos: float, franja: str) -> None:
    while True:
        time.sleep(minutos * 60)
        if not _en_franja(franja):
            continue
        try:
            with urllib.request.urlopen(url, timeout=30) as r:  # nosec B310 - URL propia (https) definida por Render
                log.info("keepalive %s -> %s", url, r.status)
        except Exception as e:  # noqa: BLE001 - nunca debe tumbar el servicio
            log.warning("keepalive %s falló: %s", url, e)


def iniciar() -> bool:
    """Arranca el hilo una sola vez. Devuelve True si quedó activo."""
    global _iniciado
    base = os.getenv("KEEPALIVE_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if _iniciado or not base or os.getenv("KEEPALIVE", "1") == "0" or not base.startswith("https://"):
        return False
    url = base.rstrip("/") + "/health"
    minutos = float(os.getenv("KEEPALIVE_MINUTOS", "10"))
    franja = os.getenv("KEEPALIVE_HORAS", "0-24")
    threading.Thread(target=_bucle, args=(url, minutos, franja), daemon=True, name="keepalive").start()
    _iniciado = True
    log.info("keepalive activo: %s cada %s min (franja %s)", url, minutos, franja)
    return True
