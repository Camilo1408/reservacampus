import logging
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .database import Base, SessionLocal, engine, get_db
from .models import Usuario
from .schemas import LoginIn, RegistroIn, TokenOut, UsuarioOut
from .security import LimitadorIntentos, crear_token, decodificar_token, hash_password, verificar_password

log = logging.getLogger("auth")
limitador = LimitadorIntentos()
bearer = HTTPBearer(auto_error=False)


def sembrar_admin():
    with SessionLocal() as db:
        if not db.scalar(select(Usuario).where(Usuario.email == config.ADMIN_EMAIL)):
            db.add(Usuario(nombre="Administrador", email=config.ADMIN_EMAIL,
                           password_hash=hash_password(config.ADMIN_PASSWORD), rol="admin"))
            db.commit()
            log.info("Usuario administrador creado")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    sembrar_admin()
    yield


app = FastAPI(
    title="Auth Service · ReservaCampus",
    description="Registro, inicio de sesión y emisión de tokens JWT.",
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
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(bearer),
                   db: Session = Depends(get_db)) -> Usuario:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token requerido")
    try:
        datos = decodificar_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")
    usuario = db.get(Usuario, int(datos["sub"]))
    if not usuario:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no existe")
    return usuario


@app.get("/health", tags=["sistema"])
def health():
    return {"servicio": "auth", "estado": "ok"}


@app.post("/registro", response_model=UsuarioOut, status_code=201, tags=["auth"])
def registro(datos: RegistroIn, db: Session = Depends(get_db)):
    email = datos.email.lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya está registrado")
    usuario = Usuario(nombre=datos.nombre, email=email, password_hash=hash_password(datos.password))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@app.post("/login", response_model=TokenOut, tags=["auth"])
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)):
    clave = request.client.host if request.client else "desconocido"
    if limitador.bloqueado(clave):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos fallidos. Intenta en 5 minutos.")
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos.email.lower()))
    if not usuario or not verificar_password(datos.password, usuario.password_hash):
        limitador.registrar_fallo(clave)
        # Mensaje genérico para no revelar si el correo existe
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    limitador.reiniciar(clave)
    return TokenOut(access_token=crear_token(usuario), expira_en_min=config.JWT_EXP_MIN, usuario=usuario)


@app.get("/me", response_model=UsuarioOut, tags=["auth"])
def me(usuario: Usuario = Depends(usuario_actual)):
    return usuario


@app.get("/usuarios", response_model=list[UsuarioOut], tags=["admin"])
def listar_usuarios(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if usuario.rol != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo administradores")
    return db.scalars(select(Usuario).order_by(Usuario.id)).all()
