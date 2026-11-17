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
