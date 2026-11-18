import hashlib
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import inspect, or_, select, text
from sqlalchemy.orm import Session

from . import config
from .database import Base, SessionLocal, engine, get_db
from .eventos import publicador
from .models import Usuario
from .schemas import (CambiarPasswordIn, EstadoIn, LoginIn, RecuperarIn, RegistroIn, RestablecerIn, RolIn, TokenOut,
                      UsuarioOut)
from .security import LimitadorIntentos, crear_token, decodificar_token, hash_password, verificar_password

log = logging.getLogger("auth")
limitador = LimitadorIntentos()
limitador_recuperar = LimitadorIntentos(maximo=5, ventana_seg=900)
bearer = HTTPBearer(auto_error=False)

COLUMNAS_NUEVAS = {
    "estado": "VARCHAR(20) DEFAULT 'activo' NOT NULL",
    "motivo_estado": "VARCHAR(300)",
    "reset_token_hash": "VARCHAR(128)",
    "reset_expira": "TIMESTAMP WITH TIME ZONE",
    "ultimo_acceso": "TIMESTAMP WITH TIME ZONE",
}


def migrar():
    """Agrega columnas nuevas a una tabla existente (create_all no altera tablas)."""
    insp = inspect(engine)
    if "usuarios" not in insp.get_table_names():
        return
    existentes = {c["name"] for c in insp.get_columns("usuarios")}
    with engine.begin() as con:
        for col, ddl in COLUMNAS_NUEVAS.items():
            if col not in existentes:
                if engine.dialect.name == "sqlite":
                    ddl = ddl.replace("TIMESTAMP WITH TIME ZONE", "DATETIME")
                con.execute(text(f"ALTER TABLE usuarios ADD COLUMN {col} {ddl}"))


def sembrar_admin():
    with SessionLocal() as db:
        if not db.scalar(select(Usuario).where(Usuario.email == config.ADMIN_EMAIL)):
            db.add(Usuario(nombre="Administrador", email=config.ADMIN_EMAIL,
                           password_hash=hash_password(config.ADMIN_PASSWORD), rol="admin"))
            db.commit()
            log.info("Usuario administrador creado")


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrar()
    Base.metadata.create_all(engine)
    sembrar_admin()
    yield


app = FastAPI(
    title="Auth Service · ReservaCampus",
    description="Registro, inicio de sesión, JWT, estados de cuenta (activo/suspendido/bloqueado), "
                "recuperación de contraseña y gestión de usuarios para el administrador.",
    version="1.2.0",
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


# ---------------------------------------------------------------- dependencias
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
    if usuario.estado == "bloqueado":
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Tu cuenta está bloqueada: {usuario.motivo_estado or ''}")
    return usuario


def solo_admin(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo administradores")
    return u


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generar_enlace_reset(db: Session, u: Usuario) -> str:
    """Token aleatorio de un solo uso; en BD solo se guarda su hash."""
    token = secrets.token_urlsafe(32)
    u.reset_token_hash = _hash_token(token)
    u.reset_expira = datetime.now(timezone.utc) + timedelta(minutes=config.RESET_MINUTOS)
    db.commit()
    return f"{config.FRONTEND_URL}/?reset={token}"


def evento_usuario(u: Usuario, **extra) -> dict:
    return {"usuario_id": u.id, "usuario_email": u.email, "usuario_nombre": u.nombre, **extra}


# ---------------------------------------------------------------- públicos
@app.get("/health", tags=["sistema"])
def health():
    return {"servicio": "auth", "estado": "ok", "cola_eventos": publicador.disponible()}


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
    if usuario.estado == "bloqueado":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Tu cuenta está bloqueada. Motivo: {usuario.motivo_estado or 'sin especificar'}. "
                            "Comunícate con soporte@reservacampus.edu")
    limitador.reiniciar(clave)
    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    return TokenOut(access_token=crear_token(usuario), expira_en_min=config.JWT_EXP_MIN, usuario=usuario)


@app.post("/recuperar", tags=["auth"])
def recuperar_password(datos: RecuperarIn, request: Request, db: Session = Depends(get_db)):
    """Envía un enlace para restablecer la contraseña. Responde igual exista o no el correo."""
    clave = request.client.host if request.client else "desconocido"
    if limitador_recuperar.bloqueado(clave):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiadas solicitudes. Intenta más tarde.")
    limitador_recuperar.registrar_fallo(clave)
    u = db.scalar(select(Usuario).where(Usuario.email == datos.email.lower()))
    if u and u.estado != "bloqueado":
        enlace = generar_enlace_reset(db, u)
        publicador.publicar("usuario.password_reset", evento_usuario(u, enlace=enlace, minutos=config.RESET_MINUTOS))
    return {"mensaje": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."}


@app.post("/restablecer", tags=["auth"])
def restablecer_password(datos: RestablecerIn, db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(Usuario.reset_token_hash == _hash_token(datos.token)))
    ahora = datetime.now(timezone.utc)
    expira = u.reset_expira.replace(tzinfo=timezone.utc) if u and u.reset_expira and u.reset_expira.tzinfo is None \
        else (u.reset_expira if u else None)
    if not u or not expira or expira < ahora:
        raise HTTPException(400, "El enlace no es válido o ya expiró. Solicita uno nuevo.")
    u.password_hash = hash_password(datos.password)
    u.reset_token_hash = None
    u.reset_expira = None
    db.commit()
    publicador.publicar("usuario.password_cambiada", evento_usuario(u))
    return {"mensaje": "Contraseña actualizada. Ya puedes iniciar sesión."}


@app.get("/me", response_model=UsuarioOut, tags=["auth"])
def me(usuario: Usuario = Depends(usuario_actual)):
    return usuario


@app.post("/me/password", tags=["auth"])
def cambiar_password(datos: CambiarPasswordIn, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if not verificar_password(datos.actual, u.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta")
    u.password_hash = hash_password(datos.nueva)
    db.commit()
    return {"mensaje": "Contraseña actualizada"}


# ---------------------------------------------------------------- administración de usuarios
@app.get("/usuarios", response_model=list[UsuarioOut], tags=["admin"])
def listar_usuarios(q: str | None = Query(None, max_length=80), estado: str | None = None,
                    _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    consulta = select(Usuario)
    if q:
        patron = f"%{q.lower()}%"
        consulta = consulta.where(or_(Usuario.email.ilike(patron), Usuario.nombre.ilike(patron)))
    if estado:
        consulta = consulta.where(Usuario.estado == estado)
    return db.scalars(consulta.order_by(Usuario.nombre)).all()


@app.get("/usuarios/{uid}", response_model=UsuarioOut, tags=["admin"])
def obtener_usuario(uid: int, _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    return u


@app.patch("/usuarios/{uid}/estado", response_model=UsuarioOut, tags=["admin"])
def cambiar_estado(uid: int, datos: EstadoIn, admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """activo: normal · suspendido: puede entrar pero no reservar · bloqueado: no puede iniciar sesión."""
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id:
        raise HTTPException(409, "No puedes cambiar el estado de tu propia cuenta")
    u.estado = datos.estado
    u.motivo_estado = datos.motivo or None
    db.commit()
    publicador.publicar("usuario.estado_cambiado",
                        evento_usuario(u, estado=datos.estado, motivo=datos.motivo or "Cuenta reactivada",
                                       admin=admin.nombre))
    return u


@app.patch("/usuarios/{uid}/rol", response_model=UsuarioOut, tags=["admin"])
def cambiar_rol(uid: int, datos: RolIn, admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id:
        raise HTTPException(409, "No puedes cambiar tu propio rol")
    u.rol = datos.rol
    db.commit()
    return u


@app.post("/usuarios/{uid}/restablecer", tags=["admin"])
def admin_restablecer(uid: int, admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Genera un enlace de recuperación y lo envía al correo del usuario. El enlace también se devuelve
    al administrador para compartirlo por otro medio si el correo no llega."""
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    enlace = generar_enlace_reset(db, u)
    publicador.publicar("usuario.password_reset",
                        evento_usuario(u, enlace=enlace, minutos=config.RESET_MINUTOS, admin=admin.nombre))
    return {"mensaje": f"Se envió un enlace de recuperación a {u.email}", "enlace": enlace,
            "expira_en_min": config.RESET_MINUTOS}
