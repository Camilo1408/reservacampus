from contextlib import asynccontextmanager
from datetime import datetime

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import config
from .consumidor import Consumidor, enviar_correo
from .database import Base, engine, get_db
from .models import Notificacion

bearer = HTTPBearer(auto_error=False)
consumidor = Consumidor()


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    titulo: str
    mensaje: str
    leida: bool
    correo_enviado: bool
    creada_en: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumidor
    Base.metadata.create_all(engine)
    consumidor = Consumidor()
    consumidor.start()
    yield
    consumidor.detener.set()


app = FastAPI(
    title="Notificaciones Service · ReservaCampus",
    description="Consume eventos de reservas desde Redis Streams, genera notificaciones en la app "
                "y (opcional) envía correo por SMTP.",
    version="1.0.0",
    root_path=config.ROOT_PATH,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


def usuario_id(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debes iniciar sesión")
    try:
        return int(jwt.decode(cred.credentials, config.JWT_SECRET, algorithms=["HS256"])["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")


@app.get("/health", tags=["sistema"])
def health():
    return {"servicio": "notificaciones", "estado": "ok", "cola_conectada": consumidor.conectado,
            "eventos_procesados": consumidor.procesados, "correo_configurado": bool(config.BREVO_API_KEY or config.SMTP_HOST)}


@app.get("/notificaciones", response_model=list[NotificacionOut], tags=["notificaciones"])
def mis_notificaciones(uid: int = Depends(usuario_id), db: Session = Depends(get_db)):
    q = select(Notificacion).where(Notificacion.usuario_id == uid).order_by(Notificacion.id.desc()).limit(30)
    return db.scalars(q).all()


@app.post("/notificaciones/{nid}/leer", response_model=NotificacionOut, tags=["notificaciones"])
def marcar_leida(nid: int, uid: int = Depends(usuario_id), db: Session = Depends(get_db)):
    n = db.get(Notificacion, nid)
    if not n or n.usuario_id != uid:
        raise HTTPException(404, "Notificación no encontrada")
    n.leida = True
    db.commit()
    return n


@app.post("/notificaciones/leer-todas", tags=["notificaciones"])
def marcar_todas(uid: int = Depends(usuario_id), db: Session = Depends(get_db)):
    db.execute(update(Notificacion).where(Notificacion.usuario_id == uid).values(leida=True))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- alertas del administrador
class AlertaIn(BaseModel):
    usuario_id: int
    usuario_email: str = Field(max_length=120)
    usuario_nombre: str = Field(max_length=80)
    asunto: str = Field(min_length=3, max_length=100)
    mensaje: str = Field(min_length=10, max_length=500)
    enviar_correo: bool = True

    @field_validator("asunto", "mensaje")
    @classmethod
    def limpiar(cls, v: str) -> str:
        return v.replace("<", "").replace(">", "").strip()


def admin_actual(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debes iniciar sesión")
    try:
        datos = jwt.decode(cred.credentials, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")
    if datos.get("rol") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo administradores")
    return datos


@app.post("/alertas", response_model=NotificacionOut, status_code=201, tags=["admin"])
def enviar_alerta(datos: AlertaIn, admin: dict = Depends(admin_actual), db: Session = Depends(get_db)):
    """El administrador advierte a un usuario sobre su comportamiento (notificación en la app + correo)."""
    n = Notificacion(usuario_id=datos.usuario_id, email=datos.usuario_email, tipo="alerta.admin",
                     titulo=f"⚠️ {datos.asunto}", mensaje=datos.mensaje, evento_id=f"alerta-{uuid.uuid4().hex}")
    if datos.enviar_correo:
        n.correo_enviado = enviar_correo(datos.usuario_email, datos.usuario_nombre, n.titulo,
                                         f"{datos.mensaje} — Administración ({admin.get('nombre', '')})")
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


@app.get("/admin/usuarios/{uid}/notificaciones", response_model=list[NotificacionOut], tags=["admin"])
def notificaciones_de_usuario(uid: int, _: dict = Depends(admin_actual), db: Session = Depends(get_db)):
    return db.scalars(select(Notificacion).where(Notificacion.usuario_id == uid)
                      .order_by(Notificacion.id.desc()).limit(100)).all()
