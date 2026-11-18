"""Publicador de eventos de dominio sobre Redis Streams (comunicación asíncrona)."""
import json
import logging
import threading
import urllib.request
from datetime import datetime, timezone

import redis

from . import config

log = logging.getLogger("eventos")


class Publicador:
    def __init__(self, url: str):
        self.cliente = redis.Redis.from_url(url, socket_timeout=3) if url else None
        self.enviados: list[dict] = []  # memoria local (útil en pruebas y modo sin Redis)

    def publicar(self, tipo: str, datos: dict) -> bool:
        evento = {"tipo": tipo, "datos": json.dumps(datos, default=str),
                  "emitido_en": datetime.now(timezone.utc).isoformat()}
        self.enviados.append(evento)
        if not self.cliente:
            log.info("Redis no configurado; evento %s solo registrado localmente", tipo)
            return False
        try:
            self.cliente.xadd(config.STREAM_EVENTOS, evento, maxlen=10000, approximate=True)
            self._despertar_consumidor()
            return True
        except redis.RedisError as e:
            # La operación de negocio no debe fallar si la cola está caída
            log.error("No se pudo publicar evento %s: %s", tipo, e)
            return False

    def _despertar_consumidor(self):
        """En Render gratuito los servicios duermen sin tráfico HTTP. Un GET a /health del servicio de
        notificaciones lo despierta y su consumidor procesa los eventos pendientes del stream."""
        url = getattr(config, "NOTIF_URL", "")
        if not url:
            return

        def ping():
            try:
                urllib.request.urlopen(f"{url}/health", timeout=60).read()
            except Exception:
                pass
        threading.Thread(target=ping, daemon=True).start()

    def disponible(self) -> bool:
        if not self.cliente:
            return False
        try:
            return bool(self.cliente.ping())
        except redis.RedisError:
            return False


publicador = Publicador(config.REDIS_URL)
