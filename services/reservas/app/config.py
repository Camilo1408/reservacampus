import os
from zoneinfo import ZoneInfo


def normalizar_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalizar_db_url(os.getenv("DATABASE_URL", "sqlite:///./reservas.db"))
REDIS_URL = os.getenv("REDIS_URL", "")
STREAM_EVENTOS = os.getenv("STREAM_EVENTOS", "eventos.reservas")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-cambiar")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ROOT_PATH = os.getenv("ROOT_PATH", "")
ZONA = ZoneInfo(os.getenv("APP_TZ", "America/Bogota"))

# Reglas de negocio
DURACION_MIN = 30          # minutos
DURACION_MAX = 180         # minutos
DIAS_ANTICIPACION = 30
MAX_RESERVAS_ACTIVAS = 3

# Integraciones
AUTH_URL = os.getenv("AUTH_URL", "").rstrip("/")        # para consultar el estado de la cuenta al reservar
NOTIF_URL = os.getenv("NOTIF_URL", "").rstrip("/")      # para despertar al consumidor en Render gratuito
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080").rstrip("/")
TAREAS_TOKEN = os.getenv("TAREAS_TOKEN", "")            # protege POST /tareas/ejecutar (cron externo)
TAREAS_INTERVALO_SEG = int(os.getenv("TAREAS_INTERVALO_SEG", "60"))

# Llegada y reportes (minutos)
RECORDATORIO_ANTES = 10      # aviso previo al inicio
TOLERANCIA_ENTREGA = 10      # el ocupante anterior tiene 10 min para entregar el espacio
AVISO_SIN_CONFIRMAR = 10     # segundo aviso si no ha confirmado llegada
LIMITE_CONFIRMACION = 20     # sin confirmar a los 20 min -> inasistencia y sanción
