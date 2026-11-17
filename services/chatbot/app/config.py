import os
from zoneinfo import ZoneInfo

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
RESERVAS_URL = os.getenv("RESERVAS_URL", "http://localhost:8002").rstrip("/")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
ROOT_PATH = os.getenv("ROOT_PATH", "")
ZONA = ZoneInfo(os.getenv("APP_TZ", "America/Bogota"))
MAX_MENSAJES_POR_MINUTO = int(os.getenv("CHAT_RATE_LIMIT", "15"))
