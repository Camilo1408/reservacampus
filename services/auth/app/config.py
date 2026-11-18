import os


def normalizar_db_url(url: str) -> str:
    """Render entrega postgres://; SQLAlchemy + psycopg3 necesita postgresql+psycopg://"""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalizar_db_url(os.getenv("DATABASE_URL", "sqlite:///./auth.db"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-cambiar")
JWT_ALG = "HS256"
JWT_EXP_MIN = int(os.getenv("JWT_EXP_MIN", "120"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ROOT_PATH = os.getenv("ROOT_PATH", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@reservacampus.edu")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin12345")
REDIS_URL = os.getenv("REDIS_URL", "")
STREAM_EVENTOS = os.getenv("STREAM_EVENTOS", "eventos.reservas")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080").rstrip("/")
NOTIF_URL = os.getenv("NOTIF_URL", "").rstrip("/")
RESET_MINUTOS = int(os.getenv("RESET_MINUTOS", "30"))
