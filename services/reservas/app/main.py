import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, time

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .database import Base, SessionLocal, engine, get_db
from .deps import UsuarioToken, solo_admin, usuario_actual
from .eventos import publicador
from .models import Espacio, Reserva
from .reglas import ReglaVioladaError, se_solapan, validar_capacidad, validar_horario
from .schemas import DisponibilidadOut, EspacioIn, EspacioOut, Franja, ReservaIn, ReservaOut

log = logging.getLogger("reservas")

ESPACIOS_INICIALES = [
    dict(nombre="Sala de Estudio A-101", tipo="sala_estudio", capacidad=6, ubicacion="Biblioteca, piso 1",
         descripcion="Mesa para 6, tablero y TV para presentaciones."),
    dict(nombre="Sala de Estudio A-102", tipo="sala_estudio", capacidad=4, ubicacion="Biblioteca, piso 1",
         descripcion="Sala pequeña y silenciosa."),
    dict(nombre="Sala de Estudio B-201", tipo="sala_estudio", capacidad=10, ubicacion="Biblioteca, piso 2",
         descripcion="Sala grupal con videobeam."),
    dict(nombre="Laboratorio de Cómputo 1", tipo="laboratorio", capacidad=30, ubicacion="Bloque C, piso 3",
         descripcion="30 equipos con Python, Docker y VS Code.", hora_apertura=time(7, 0), hora_cierre=time(20, 0)),
    dict(nombre="Laboratorio de Redes", tipo="laboratorio", capacidad=20, ubicacion="Bloque C, piso 2",
         descripcion="Switches, routers y racks para prácticas.", hora_apertura=time(8, 0), hora_cierre=time(18, 0)),
    dict(nombre="Auditorio Principal", tipo="auditorio", capacidad=200, ubicacion="Bloque A",
         descripcion="Sonido, proyector y tarima.", hora_apertura=time(8, 0), hora_cierre=time(20, 0)),
    dict(nombre="Cancha Múltiple", tipo="cancha", capacidad=24, ubicacion="Zona deportiva",
         descripcion="Fútbol sala, baloncesto y voleibol.", hora_apertura=time(6, 0), hora_cierre=time(22, 0)),
]


def sembrar_espacios():
    with SessionLocal() as db:
        if not db.scalar(select(func.count(Espacio.id))):
            db.add_all(Espacio(**e) for e in ESPACIOS_INICIALES)
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    sembrar_espacios()
    yield


app = FastAPI(
    title="Reservas Service · ReservaCampus",
    description="Gestión de espacios y reservas. Publica eventos `reserva.creada` y `reserva.cancelada` "
                "en Redis Streams para el servicio de notificaciones.",
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


def a_salida(r: Reserva) -> ReservaOut:
    return ReservaOut(espacio_nombre=r.espacio.nombre, **{k: getattr(r, k) for k in ReservaOut.model_fields
                                                           if k != "espacio_nombre"})


def evento_reserva(r: Reserva) -> dict:
    return {"reserva_id": r.id, "usuario_id": r.usuario_id, "usuario_email": r.usuario_email,
            "usuario_nombre": r.usuario_nombre, "espacio": r.espacio.nombre, "fecha": r.fecha.isoformat(),
            "hora_inicio": r.hora_inicio.strftime("%H:%M"), "hora_fin": r.hora_fin.strftime("%H:%M")}


def ocupacion(db: Session, espacio_id: int, fecha: date) -> list[Reserva]:
    return db.scalars(select(Reserva).where(Reserva.espacio_id == espacio_id, Reserva.fecha == fecha,
                                            Reserva.estado == "confirmada").order_by(Reserva.hora_inicio)).all()


# ---------------------------------------------------------------- sistema
@app.get("/health", tags=["sistema"])
def health():
    return {"servicio": "reservas", "estado": "ok", "cola_eventos": publicador.disponible()}


# ---------------------------------------------------------------- espacios
@app.get("/espacios", response_model=list[EspacioOut], tags=["espacios"])
def listar_espacios(tipo: str | None = None, capacidad_min: int = Query(0, ge=0),
                    db: Session = Depends(get_db)):
    q = select(Espacio).where(Espacio.activo.is_(True), Espacio.capacidad >= capacidad_min)
    if tipo:
        q = q.where(Espacio.tipo == tipo)
    return db.scalars(q.order_by(Espacio.tipo, Espacio.nombre)).all()


@app.get("/espacios/{espacio_id}", response_model=EspacioOut, tags=["espacios"])
def obtener_espacio(espacio_id: int, db: Session = Depends(get_db)):
    e = db.get(Espacio, espacio_id)
    if not e:
        raise HTTPException(404, "Espacio no encontrado")
    return e


@app.post("/espacios", response_model=EspacioOut, status_code=201, tags=["espacios"])
def crear_espacio(datos: EspacioIn, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Espacio).where(Espacio.nombre == datos.nombre)):
        raise HTTPException(409, "Ya existe un espacio con ese nombre")
    e = Espacio(**datos.model_dump())
    db.add(e)
    db.commit()
    return e


@app.put("/espacios/{espacio_id}", response_model=EspacioOut, tags=["espacios"])
def actualizar_espacio(espacio_id: int, datos: EspacioIn, _: UsuarioToken = Depends(solo_admin),
                       db: Session = Depends(get_db)):
    e = db.get(Espacio, espacio_id)
    if not e:
        raise HTTPException(404, "Espacio no encontrado")
    for k, v in datos.model_dump().items():
        setattr(e, k, v)
    db.commit()
    return e


@app.get("/espacios/{espacio_id}/ocupacion", response_model=list[Franja], tags=["espacios"])
def ocupacion_espacio(espacio_id: int, fecha: date, db: Session = Depends(get_db)):
    return [Franja(hora_inicio=r.hora_inicio, hora_fin=r.hora_fin) for r in ocupacion(db, espacio_id, fecha)]


@app.get("/disponibilidad", response_model=list[DisponibilidadOut], tags=["espacios"])
def disponibilidad(fecha: date | None = None, hora_inicio: time | None = None, hora_fin: time | None = None,
                   tipo: str | None = None, db: Session = Depends(get_db)):
    """Estado de todos los espacios en una fecha. Si se envía un rango horario, `libre` indica
    si el espacio está disponible en ese rango; si no, indica si no tiene reservas ese día."""
    fecha = fecha or datetime.now(config.ZONA).date()
    salida = []
    for e in listar_espacios(tipo=tipo, capacidad_min=0, db=db):
        ocupadas = ocupacion(db, e.id, fecha)
        if hora_inicio and hora_fin:
            dentro = e.hora_apertura <= hora_inicio and hora_fin <= e.hora_cierre
            libre = dentro and not any(se_solapan(hora_inicio, hora_fin, r.hora_inicio, r.hora_fin) for r in ocupadas)
        else:
            libre = not ocupadas
        salida.append(DisponibilidadOut(espacio=e, fecha=fecha, libre=libre,
                                        ocupado=[Franja(hora_inicio=r.hora_inicio, hora_fin=r.hora_fin) for r in ocupadas]))
    return salida


# ---------------------------------------------------------------- reservas
@app.post("/reservas", response_model=ReservaOut, status_code=201, tags=["reservas"])
def crear_reserva(datos: ReservaIn, u: UsuarioToken = Depends(usuario_actual), db: Session = Depends(get_db)):
    # Bloqueo pesimista de la fila del espacio para evitar dobles reservas concurrentes (Postgres)
    espacio = db.scalar(select(Espacio).where(Espacio.id == datos.espacio_id).with_for_update())
    if not espacio or not espacio.activo:
        raise HTTPException(404, "Espacio no encontrado")
    try:
        validar_horario(datos.fecha, datos.hora_inicio, datos.hora_fin, espacio.hora_apertura, espacio.hora_cierre)
        validar_capacidad(datos.asistentes, espacio.capacidad)
    except ReglaVioladaError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    for r in ocupacion(db, espacio.id, datos.fecha):
        if se_solapan(datos.hora_inicio, datos.hora_fin, r.hora_inicio, r.hora_fin):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"El espacio ya está reservado de {r.hora_inicio:%H:%M} a {r.hora_fin:%H:%M}")

    hoy = datetime.now(config.ZONA).date()
    activas = db.scalar(select(func.count(Reserva.id)).where(
        Reserva.usuario_id == u.id, Reserva.estado == "confirmada", Reserva.fecha >= hoy))
    if activas >= config.MAX_RESERVAS_ACTIVAS and not u.es_admin:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Ya tienes {config.MAX_RESERVAS_ACTIVAS} reservas activas. Cancela alguna para reservar otra.")

    reserva = Reserva(espacio_id=espacio.id, usuario_id=u.id, usuario_email=u.email, usuario_nombre=u.nombre,
                      **datos.model_dump(exclude={"espacio_id"}))
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    publicador.publicar("reserva.creada", evento_reserva(reserva))
    return a_salida(reserva)


@app.get("/reservas/mias", response_model=list[ReservaOut], tags=["reservas"])
def mis_reservas(solo_activas: bool = False, u: UsuarioToken = Depends(usuario_actual), db: Session = Depends(get_db)):
    q = select(Reserva).where(Reserva.usuario_id == u.id)
    if solo_activas:
        q = q.where(Reserva.estado == "confirmada", Reserva.fecha >= datetime.now(config.ZONA).date())
    return [a_salida(r) for r in db.scalars(q.order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc())).all()]


@app.get("/reservas", response_model=list[ReservaOut], tags=["reservas"])
def todas_las_reservas(fecha: date | None = None, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    q = select(Reserva)
    if fecha:
        q = q.where(Reserva.fecha == fecha)
    return [a_salida(r) for r in db.scalars(q.order_by(Reserva.fecha.desc(), Reserva.hora_inicio)).all()]


@app.post("/reservas/{reserva_id}/cancelar", response_model=ReservaOut, tags=["reservas"])
def cancelar_reserva(reserva_id: int, u: UsuarioToken = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = db.get(Reserva, reserva_id)
    # Control de acceso: solo el dueño o un admin (evita IDOR, OWASP A01)
    if not r or (r.usuario_id != u.id and not u.es_admin):
        raise HTTPException(404, "Reserva no encontrada")
    if r.estado == "cancelada":
        raise HTTPException(409, "La reserva ya estaba cancelada")
    r.estado = "cancelada"
    db.commit()
    publicador.publicar("reserva.cancelada", {**evento_reserva(r), "cancelada_por": u.nombre})
    return a_salida(r)


@app.get("/estadisticas", tags=["admin"])
def estadisticas(_: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    por_espacio = db.execute(
        select(Espacio.nombre, func.count(Reserva.id))
        .join(Reserva, Reserva.espacio_id == Espacio.id)
        .where(Reserva.estado == "confirmada")
        .group_by(Espacio.nombre).order_by(func.count(Reserva.id).desc())).all()
    total = db.scalar(select(func.count(Reserva.id)))
    canceladas = db.scalar(select(func.count(Reserva.id)).where(Reserva.estado == "cancelada"))
    return {"total_reservas": total, "canceladas": canceladas,
            "por_espacio": [{"espacio": n, "reservas": c} for n, c in por_espacio]}
