import logging
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, time

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.orm import Session

from . import config
from .database import Base, SessionLocal, engine, get_db
from .deps import UsuarioToken, solo_admin, usuario_actual
from .eventos import publicador
from .models import Espacio, HorarioClase, Reporte, Reserva, Sancion
from .reglas import ReglaVioladaError, se_solapan, validar_capacidad, validar_horario
from .schemas import (CargaHorariosIn, ConflictoOut, DisponibilidadOut, EspacioIn, EspacioOut, EstadoEspacioIn,
                      Franja, HorarioIn, HorarioOut, ReservaIn, ReservaOut, ResultadoCarga, RevocarIn)
from .semilla import ESPACIOS_INICIALES, HORARIOS_INICIALES
from . import reloj, sanciones
from .incidencias import router as router_incidencias
from .tareas import Programador

programador = Programador()

log = logging.getLogger("reservas")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


COLUMNAS_NUEVAS = {
    "reservas": {
        "motivo_revocacion": "VARCHAR(300)",
        "llegada_confirmada_en": "TIMESTAMP",
        "aviso_previo": "BOOLEAN DEFAULT FALSE NOT NULL",
        "aviso_inicio": "BOOLEAN DEFAULT FALSE NOT NULL",
        "aviso_final": "BOOLEAN DEFAULT FALSE NOT NULL",
    },
    "espacios": {
        "actividades": "VARCHAR(300) DEFAULT '' NOT NULL",
    },
}


def migrar():
    """Migración ligera: agrega columnas nuevas a tablas ya existentes (create_all no altera tablas)."""
    insp = inspect(engine)
    tablas = insp.get_table_names()
    with engine.begin() as con:
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            if tabla not in tablas:
                continue
            existentes = {c["name"] for c in insp.get_columns(tabla)}
            for col, ddl in columnas.items():
                if col not in existentes:
                    con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {col} {ddl}"))


def sembrar():
    with SessionLocal() as db:
        if not db.scalar(select(func.count(Espacio.id))):
            db.add_all(Espacio(**e) for e in ESPACIOS_INICIALES)
            db.commit()
        # Espacios iniciales creados antes de existir el campo "actividades": completarlo una sola vez
        semilla = {e["nombre"]: e.get("actividades", "") for e in ESPACIOS_INICIALES}
        for e in db.scalars(select(Espacio).where(Espacio.actividades == "")):
            if semilla.get(e.nombre):
                e.actividades = semilla[e.nombre]
        db.commit()
        if not db.scalar(select(func.count(HorarioClase.id))):
            por_nombre = {e.nombre: e.id for e in db.scalars(select(Espacio))}
            for h in HORARIOS_INICIALES:
                if h["espacio"] in por_nombre:
                    db.add(HorarioClase(espacio_id=por_nombre[h["espacio"]], dia_semana=h["dia"],
                                        hora_inicio=h["inicio"], hora_fin=h["fin"], materia=h["materia"],
                                        docente=h.get("docente", "")))
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrar()
    Base.metadata.create_all(engine)
    sembrar()
    if config.TAREAS_INTERVALO_SEG > 0:
        programador.start()
    yield
    programador.detener.set()


app = FastAPI(
    title="Reservas Service · ReservaCampus",
    description="Gestión de espacios, horarios de clase y reservas. Publica eventos `reserva.creada`, "
                "`reserva.cancelada` y `reserva.revocada` en Redis Streams para el servicio de notificaciones.",
    version="1.1.0",
    root_path=config.ROOT_PATH,
    lifespan=lifespan,
)
app.include_router(router_incidencias)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


# ---------------------------------------------------------------- utilidades
def a_salida(r: Reserva) -> ReservaOut:
    return ReservaOut(espacio_nombre=r.espacio.nombre, **{k: getattr(r, k) for k in ReservaOut.model_fields
                                                           if k != "espacio_nombre"})


def horario_salida(h: HorarioClase) -> HorarioOut:
    return HorarioOut(espacio_nombre=h.espacio.nombre, **{k: getattr(h, k) for k in HorarioOut.model_fields
                                                          if k != "espacio_nombre"})


def evento_reserva(r: Reserva) -> dict:
    return {"reserva_id": r.id, "usuario_id": r.usuario_id, "usuario_email": r.usuario_email,
            "usuario_nombre": r.usuario_nombre, "espacio": r.espacio.nombre, "fecha": r.fecha.isoformat(),
            "hora_inicio": r.hora_inicio.strftime("%H:%M"), "hora_fin": r.hora_fin.strftime("%H:%M")}


def reservas_del_dia(db: Session, espacio_id: int, fecha: date) -> list[Reserva]:
    return db.scalars(select(Reserva).where(Reserva.espacio_id == espacio_id, Reserva.fecha == fecha,
                                            Reserva.estado == "confirmada").order_by(Reserva.hora_inicio)).all()


def clases_del_dia(db: Session, espacio_id: int, fecha: date) -> list[HorarioClase]:
    hs = db.scalars(select(HorarioClase).where(HorarioClase.espacio_id == espacio_id,
                                               HorarioClase.dia_semana == fecha.weekday())).all()
    return sorted((h for h in hs if h.aplica(fecha)), key=lambda h: h.hora_inicio)


def ocupacion(db: Session, espacio_id: int, fecha: date) -> list[Franja]:
    franjas = [Franja(hora_inicio=h.hora_inicio, hora_fin=h.hora_fin, tipo="clase",
                      etiqueta=h.materia) for h in clases_del_dia(db, espacio_id, fecha)]
    franjas += [Franja(hora_inicio=r.hora_inicio, hora_fin=r.hora_fin, tipo="reserva", etiqueta="Reservado")
                for r in reservas_del_dia(db, espacio_id, fecha)]
    return sorted(franjas, key=lambda f: f.hora_inicio)


def conflictos_de_horario(db: Session, h: HorarioClase) -> list[Reserva]:
    """Reservas futuras confirmadas que chocan con un bloque de clase."""
    hoy = reloj.ahora().date()
    rs = db.scalars(select(Reserva).where(Reserva.espacio_id == h.espacio_id, Reserva.estado == "confirmada",
                                          Reserva.fecha >= hoy)).all()
    return [r for r in rs if h.aplica(r.fecha) and se_solapan(h.hora_inicio, h.hora_fin, r.hora_inicio, r.hora_fin)]


def a_conflicto(r: Reserva) -> ConflictoOut:
    return ConflictoOut(reserva_id=r.id, espacio=r.espacio.nombre, fecha=r.fecha, hora_inicio=r.hora_inicio,
                        hora_fin=r.hora_fin, usuario_nombre=r.usuario_nombre)


def revocar(db: Session, r: Reserva, justificacion: str, admin: UsuarioToken):
    r.estado = "revocada"
    r.motivo_revocacion = justificacion
    db.commit()
    publicador.publicar("reserva.revocada", {**evento_reserva(r), "justificacion": justificacion,
                                             "revocada_por": admin.nombre})


# ---------------------------------------------------------------- sistema
@app.get("/health", tags=["sistema"])
def health():
    return {"servicio": "reservas", "estado": "ok", "cola_eventos": publicador.disponible(),
            "programador_activo": programador.is_alive(),
            "ultima_ejecucion": programador.ultima_hora, "ultimo_resultado": programador.ultima}


def estado_cuenta(authorization: str | None) -> str | None:
    """Consulta al auth-service el estado actual de la cuenta (REST síncrono entre servicios).
    Si auth no responde se permite continuar (disponibilidad > consistencia para este dato)."""
    if not config.AUTH_URL or not authorization:
        return None
    import json
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(f"{config.AUTH_URL}/me", headers={"Authorization": authorization})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("estado")
    except urllib.error.HTTPError as e:
        return "bloqueado" if e.code == 403 else None
    except Exception:
        log.warning("auth-service no respondió; se omite la verificación de estado")
        return None


# ---------------------------------------------------------------- espacios
@app.get("/espacios", response_model=list[EspacioOut], tags=["espacios"])
def listar_espacios(tipo: str | None = None, capacidad_min: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = select(Espacio).where(Espacio.activo.is_(True), Espacio.capacidad >= capacidad_min)
    if tipo:
        q = q.where(Espacio.tipo == tipo)
    return db.scalars(q.order_by(Espacio.tipo, Espacio.nombre)).all()


@app.get("/admin/espacios", response_model=list[EspacioOut], tags=["admin"])
def listar_todos_los_espacios(_: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    """Incluye espacios deshabilitados."""
    return db.scalars(select(Espacio).order_by(Espacio.activo.desc(), Espacio.tipo, Espacio.nombre)).all()


@app.get("/espacios/{espacio_id}", response_model=EspacioOut, tags=["espacios"])
def obtener_espacio(espacio_id: int, db: Session = Depends(get_db)):
    e = db.get(Espacio, espacio_id)
    if not e:
        raise HTTPException(404, "Espacio no encontrado")
    return e


@app.post("/espacios", response_model=EspacioOut, status_code=201, tags=["admin"])
def crear_espacio(datos: EspacioIn, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Espacio).where(Espacio.nombre == datos.nombre)):
        raise HTTPException(409, "Ya existe un espacio con ese nombre")
    e = Espacio(**datos.model_dump())
    db.add(e)
    db.commit()
    return e


@app.put("/espacios/{espacio_id}", response_model=EspacioOut, tags=["admin"])
def actualizar_espacio(espacio_id: int, datos: EspacioIn, _: UsuarioToken = Depends(solo_admin),
                       db: Session = Depends(get_db)):
    e = db.get(Espacio, espacio_id)
    if not e:
        raise HTTPException(404, "Espacio no encontrado")
    otro = db.scalar(select(Espacio).where(Espacio.nombre == datos.nombre, Espacio.id != espacio_id))
    if otro:
        raise HTTPException(409, "Ya existe un espacio con ese nombre")
    for k, v in datos.model_dump().items():
        setattr(e, k, v)
    db.commit()
    return e


@app.patch("/espacios/{espacio_id}/estado", response_model=EspacioOut, tags=["admin"])
def cambiar_estado_espacio(espacio_id: int, datos: EstadoEspacioIn, _: UsuarioToken = Depends(solo_admin),
                           db: Session = Depends(get_db)):
    """Habilita o deshabilita un espacio. Deshabilitado no aparece para reservar; sus reservas se conservan."""
    e = db.get(Espacio, espacio_id)
    if not e:
        raise HTTPException(404, "Espacio no encontrado")
    e.activo = datos.activo
    db.commit()
    return e


@app.delete("/espacios/{espacio_id}", status_code=204, tags=["admin"])
def eliminar_espacio(espacio_id: int, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    e = db.get(Espacio, espacio_id)
    if not e:
        raise HTTPException(404, "Espacio no encontrado")
    hoy = reloj.ahora().date()
    pendientes = db.scalar(select(func.count(Reserva.id)).where(
        Reserva.espacio_id == espacio_id, Reserva.estado == "confirmada", Reserva.fecha >= hoy))
    if pendientes:
        raise HTTPException(409, f"El espacio tiene {pendientes} reserva(s) futuras. Revócalas o deshabilita "
                                 "el espacio en lugar de eliminarlo.")
    db.execute(delete(Reserva).where(Reserva.espacio_id == espacio_id))
    db.delete(e)
    db.commit()


@app.get("/espacios/{espacio_id}/ocupacion", response_model=list[Franja], tags=["espacios"])
def ocupacion_espacio(espacio_id: int, fecha: date, db: Session = Depends(get_db)):
    return ocupacion(db, espacio_id, fecha)


@app.get("/disponibilidad", response_model=list[DisponibilidadOut], tags=["espacios"])
def disponibilidad(fecha: date | None = None, hora_inicio: time | None = None, hora_fin: time | None = None,
                   tipo: str | None = None, db: Session = Depends(get_db)):
    """Estado de los espacios activos en una fecha (reservas + clases fijas). Con un rango horario, `libre`
    indica si el espacio está disponible en ese rango; si no, indica si no tiene ocupación ese día."""
    fecha = fecha or reloj.ahora().date()
    salida = []
    for e in listar_espacios(tipo=tipo, capacidad_min=0, db=db):
        ocupadas = ocupacion(db, e.id, fecha)
        if hora_inicio and hora_fin:
            dentro = e.hora_apertura <= hora_inicio and hora_fin <= e.hora_cierre
            libre = dentro and not any(se_solapan(hora_inicio, hora_fin, f.hora_inicio, f.hora_fin) for f in ocupadas)
        else:
            libre = not ocupadas
        salida.append(DisponibilidadOut(espacio=e, fecha=fecha, libre=libre, ocupado=ocupadas))
    return salida


# ---------------------------------------------------------------- horarios de clase
@app.get("/horarios", response_model=list[HorarioOut], tags=["horarios"])
def listar_horarios(espacio_id: int | None = None, db: Session = Depends(get_db)):
    q = select(HorarioClase)
    if espacio_id:
        q = q.where(HorarioClase.espacio_id == espacio_id)
    hs = db.scalars(q.order_by(HorarioClase.espacio_id, HorarioClase.dia_semana, HorarioClase.hora_inicio)).all()
    return [horario_salida(h) for h in hs]


@app.post("/horarios", response_model=ResultadoCarga, status_code=201, tags=["horarios"])
def crear_horario(datos: HorarioIn, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    if not db.get(Espacio, datos.espacio_id):
        raise HTTPException(404, "Espacio no encontrado")
    h = HorarioClase(**datos.model_dump())
    db.add(h)
    db.commit()
    return ResultadoCarga(creados=1, errores=[], conflictos=[a_conflicto(r) for r in conflictos_de_horario(db, h)])


@app.put("/horarios/{horario_id}", response_model=ResultadoCarga, tags=["horarios"])
def actualizar_horario(horario_id: int, datos: HorarioIn, _: UsuarioToken = Depends(solo_admin),
                       db: Session = Depends(get_db)):
    h = db.get(HorarioClase, horario_id)
    if not h:
        raise HTTPException(404, "Horario no encontrado")
    for k, v in datos.model_dump().items():
        setattr(h, k, v)
    db.commit()
    return ResultadoCarga(creados=0, errores=[], conflictos=[a_conflicto(r) for r in conflictos_de_horario(db, h)])


@app.delete("/horarios/{horario_id}", status_code=204, tags=["horarios"])
def eliminar_horario(horario_id: int, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    h = db.get(HorarioClase, horario_id)
    if not h:
        raise HTTPException(404, "Horario no encontrado")
    db.delete(h)
    db.commit()


def _dia(valor: str) -> int:
    v = valor.strip().lower().replace("é", "e").replace("á", "a")
    if v.isdigit() and 0 <= int(v) <= 6:
        return int(v)
    nombres = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    if v in nombres:
        return nombres.index(v)
    raise ValueError(f"día '{valor}' no reconocido")


def _hora(valor: str) -> time:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*", valor)
    if not m:
        raise ValueError(f"hora '{valor}' inválida (usa HH:MM)")
    return time(int(m[1]), int(m[2]))


@app.post("/horarios/carga", response_model=ResultadoCarga, tags=["horarios"])
def cargar_horarios(datos: CargaHorariosIn, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    """Carga masiva de horarios de clase (p. ej. desde un CSV). Si `reemplazar` es true, borra antes
    los horarios de los espacios incluidos en el archivo."""
    espacios = db.scalars(select(Espacio)).all()
    por_nombre = {e.nombre.lower(): e for e in espacios}
    por_id = {str(e.id): e for e in espacios}
    nuevos, errores = [], []
    for i, f in enumerate(datos.filas, start=2):  # fila 1 = encabezado del CSV
        try:
            esp = por_id.get(f.espacio.strip()) or por_nombre.get(f.espacio.strip().lower())
            if not esp:
                raise ValueError(f"espacio '{f.espacio}' no existe")
            h = HorarioIn(espacio_id=esp.id, dia_semana=_dia(f.dia), hora_inicio=_hora(f.hora_inicio),
                          hora_fin=_hora(f.hora_fin), materia=f.materia, docente=f.docente,
                          vigente_desde=datos.vigente_desde, vigente_hasta=datos.vigente_hasta)
            nuevos.append(h)
        except Exception as e:
            msg = e.errors()[0]["msg"] if hasattr(e, "errors") else str(e)
            errores.append(f"Fila {i}: {msg.replace('Value error, ', '')}")
    if errores:
        return ResultadoCarga(creados=0, errores=errores, conflictos=[])
    if datos.reemplazar:
        ids = {h.espacio_id for h in nuevos}
        db.execute(delete(HorarioClase).where(HorarioClase.espacio_id.in_(ids)))
    creados = [HorarioClase(**h.model_dump()) for h in nuevos]
    db.add_all(creados)
    db.commit()
    conflictos = {r.id: r for h in creados for r in conflictos_de_horario(db, h)}
    return ResultadoCarga(creados=len(creados), errores=[], conflictos=[a_conflicto(r) for r in conflictos.values()])


# ---------------------------------------------------------------- reservas
@app.post("/reservas", response_model=ReservaOut, status_code=201, tags=["reservas"])
def crear_reserva(datos: ReservaIn, request: Request, u: UsuarioToken = Depends(usuario_actual),
                  db: Session = Depends(get_db)):
    ahora = reloj.ahora()
    s = sanciones.sancion_activa(db, u.id, ahora)
    if s:
        hasta = f"hasta el {s.hasta:%d/%m/%Y a las %H:%M}" if s.hasta else "hasta que un administrador la levante"
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Tienes una sanción vigente {hasta}. Motivo: {s.motivo}")
    estado = estado_cuenta(request.headers.get("authorization"))
    if estado in ("suspendido", "bloqueado"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Tu cuenta está {estado}: no puedes hacer reservas. "
                                                       "Comunícate con la administración.")
    # Bloqueo pesimista de la fila del espacio para evitar dobles reservas concurrentes (Postgres)
    espacio = db.scalar(select(Espacio).where(Espacio.id == datos.espacio_id).with_for_update())
    if not espacio or not espacio.activo:
        raise HTTPException(404, "Espacio no encontrado o deshabilitado")
    try:
        validar_horario(datos.fecha, datos.hora_inicio, datos.hora_fin, espacio.hora_apertura, espacio.hora_cierre)
        validar_capacidad(datos.asistentes, espacio.capacidad)
    except ReglaVioladaError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    for f in ocupacion(db, espacio.id, datos.fecha):
        if se_solapan(datos.hora_inicio, datos.hora_fin, f.hora_inicio, f.hora_fin):
            causa = f"hay clase de {f.etiqueta}" if f.tipo == "clase" else "ya está reservado"
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"El espacio no está disponible: {causa} de {f.hora_inicio:%H:%M} a {f.hora_fin:%H:%M}")

    hoy = ahora.date()
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
        q = q.where(Reserva.estado == "confirmada", Reserva.fecha >= reloj.ahora().date())
    return [a_salida(r) for r in db.scalars(q.order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc())).all()]


@app.get("/reservas", response_model=list[ReservaOut], tags=["admin"])
def todas_las_reservas(fecha: date | None = None, estado: str | None = None, _: UsuarioToken = Depends(solo_admin),
                       db: Session = Depends(get_db)):
    q = select(Reserva)
    if fecha:
        q = q.where(Reserva.fecha == fecha)
    if estado:
        q = q.where(Reserva.estado == estado)
    return [a_salida(r) for r in db.scalars(q.order_by(Reserva.fecha.desc(), Reserva.hora_inicio)).all()]


@app.post("/reservas/{reserva_id}/cancelar", response_model=ReservaOut, tags=["reservas"])
def cancelar_reserva(reserva_id: int, u: UsuarioToken = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = db.get(Reserva, reserva_id)
    # Control de acceso: solo el dueño (evita IDOR, OWASP A01). El admin usa /revocar con justificación.
    if not r or r.usuario_id != u.id:
        raise HTTPException(404, "Reserva no encontrada")
    if r.estado != "confirmada":
        raise HTTPException(409, f"La reserva ya está {r.estado}")
    r.estado = "cancelada"
    db.commit()
    publicador.publicar("reserva.cancelada", {**evento_reserva(r), "cancelada_por": u.nombre})
    return a_salida(r)


@app.post("/reservas/{reserva_id}/revocar", response_model=ReservaOut, tags=["admin"])
def revocar_reserva(reserva_id: int, datos: RevocarIn, admin: UsuarioToken = Depends(solo_admin),
                    db: Session = Depends(get_db)):
    """El administrador anula una reserva con justificación. Se notifica al usuario (app + correo)."""
    r = db.get(Reserva, reserva_id)
    if not r:
        raise HTTPException(404, "Reserva no encontrada")
    if r.estado != "confirmada":
        raise HTTPException(409, f"La reserva ya está {r.estado}")
    revocar(db, r, datos.justificacion, admin)
    return a_salida(r)


@app.get("/estadisticas", tags=["admin"])
def estadisticas(_: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    por_espacio = db.execute(
        select(Espacio.nombre, func.count(Reserva.id))
        .join(Reserva, Reserva.espacio_id == Espacio.id)
        .where(Reserva.estado == "confirmada")
        .group_by(Espacio.nombre).order_by(func.count(Reserva.id).desc())).all()
    conteo = dict(db.execute(select(Reserva.estado, func.count(Reserva.id)).group_by(Reserva.estado)).all())
    return {"total_reservas": sum(conteo.values()), "confirmadas": conteo.get("confirmada", 0),
            "canceladas": conteo.get("cancelada", 0), "revocadas": conteo.get("revocada", 0),
            "espacios_activos": db.scalar(select(func.count(Espacio.id)).where(Espacio.activo.is_(True))),
            "horarios_clase": db.scalar(select(func.count(HorarioClase.id))),
            "inasistencias": conteo.get("inasistencia", 0),
            "sanciones_activas": sum(1 for x in db.scalars(select(Sancion).where(Sancion.estado == "vigente"))
                                     if x.activa(reloj.ahora())),
            "reportes": db.scalar(select(func.count(Reporte.id)).where(Reporte.estado == "valido")),
            "por_espacio": [{"espacio": n, "reservas": c} for n, c in por_espacio]}
