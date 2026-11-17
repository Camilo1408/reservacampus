import base64
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt

from .config import JWT_ALG, JWT_EXP_MIN, JWT_SECRET

ITERACIONES = 120_000


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${_b64(salt)}${_b64(dk)}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        _, it, salt, dk = almacenado.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


def crear_token(usuario) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "email": usuario.email,
        "nombre": usuario.nombre,
        "rol": usuario.rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=JWT_EXP_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


class LimitadorIntentos:
    """Bloquea una IP tras N intentos fallidos de login en una ventana de tiempo (OWASP A07)."""

    def __init__(self, maximo: int = 5, ventana_seg: int = 300):
        self.maximo = maximo
        self.ventana = ventana_seg
        self.fallos: dict[str, deque] = defaultdict(deque)

    def _limpiar(self, clave: str):
        cola = self.fallos[clave]
        limite = time.time() - self.ventana
        while cola and cola[0] < limite:
            cola.popleft()

    def bloqueado(self, clave: str) -> bool:
        self._limpiar(clave)
        return len(self.fallos[clave]) >= self.maximo

    def registrar_fallo(self, clave: str):
        self.fallos[clave].append(time.time())

    def reiniciar(self, clave: str):
        self.fallos.pop(clave, None)
