import os


def normalizar_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalizar_db_url(os.getenv("DATABASE_URL", "sqlite:///./notificaciones.db"))
REDIS_URL = os.getenv("REDIS_URL", "")
STREAM_EVENTOS = os.getenv("STREAM_EVENTOS", "eventos.reservas")
GRUPO = os.getenv("GRUPO_CONSUMIDOR", "notificaciones")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-cambiar")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ROOT_PATH = os.getenv("ROOT_PATH", "")

# Correo opcional (servicio externo). Ej.: Mailtrap, Brevo o Gmail SMTP.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "ReservaCampus <no-reply@reservacampus.edu>")

# Correo por API HTTP de Brevo (recomendado en Render; plan gratuito 300 correos/día)
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
MAIL_FROM = os.getenv("MAIL_FROM", "")           # remitente verificado en Brevo
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "ReservaCampus")
