from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

bearer = HTTPBearer(auto_error=False)


@dataclass
class UsuarioToken:
    id: int
    email: str
    nombre: str
    rol: str

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UsuarioToken:
    """Valida el JWT emitido por auth-service sin consultarlo (secreto compartido, stateless)."""
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debes iniciar sesión")
    try:
        d = jwt.decode(cred.credentials, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")
    return UsuarioToken(id=int(d["sub"]), email=d["email"], nombre=d["nombre"], rol=d.get("rol", "estudiante"))


def solo_admin(u: UsuarioToken = Depends(usuario_actual)) -> UsuarioToken:
    if not u.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo administradores")
    return u
