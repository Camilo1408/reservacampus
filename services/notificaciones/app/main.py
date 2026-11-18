from contextlib import asynccontextmanager
from datetime import datetime

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import config
from .consumidor import Consumidor
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
