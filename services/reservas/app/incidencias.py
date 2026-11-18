"""Confirmación de llegada, reportes de espacio no entregado, sanciones y vistas de administración por usuario."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config, reloj, sanciones
from .database import get_db
from .deps import UsuarioToken, solo_admin, usuario_actual
from .eventos import publicador
from .models import Reporte, Reserva, Sancion

router = APIRouter()
M = lambda n: timedelta(minutes=n)  # noqa: E731


def _limpiar(v: str) -> str:
    return v.replace("<", "").replace(">", "").strip()


# ---------------------------------------------------------------- esquemas
class ReporteIn(BaseModel):
    comentario: str = Field(default="", max_length=300)
    limpiar_texto = field_validator("comentario")(classmethod(lambda cls, v: _limpiar(v)))


class SancionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    usuario_nombre: str
    usuario_email: str
    nivel: int
    tipo: str
    motivo: str
    reserva_id: int | None
    desde: datetime
    hasta: datetime | None
    estado: str
    nota_admin: str | None
    creada_por: str
    activa: bool = False
    descripcion: str = ""


class ReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reserva_id: int
    reportante_id: int
    reportante_nombre: str
    reserva_reportada_id: int
    reportado_id: int
    reportado_nombre: str
    reportado_email: str
    espacio: str
    comentario: str
    estado: str
    sancion_id: int | None
    creado_en: datetime


class SancionManualIn(BaseModel):
    usuario_id: int
    usuario_email: str = Field(max_length=120)
    usuario_nombre: str = Field(max_length=80)
    motivo: str = Field(min_length=10, max_length=300)
    dias: int | None = Field(default=None, ge=1, le=365)  # None = indefinida
    limpiar_texto = field_validator("motivo")(classmethod(lambda cls, v: _limpiar(v)))


class NotaIn(BaseModel):
    nota: str = Field(min_length=5, max_length=300)
    limpiar_texto = field_validator("nota")(classmethod(lambda cls, v: _limpiar(v)))


def sancion_out(s: Sancion, ahora: datetime) -> SancionOut:
    campos = {k: getattr(s, k) for k in SancionOut.model_fields if k not in ("activa", "descripcion")}
    descripcion = sanciones.DESCRIPCION.get(s.nivel, "") if s.tipo != "manual" else \
        ("Sanción manual " + (f"hasta {s.hasta:%d/%m/%Y %H:%M}" if s.hasta else "indefinida"))
    return SancionOut(**campos, activa=s.activa(ahora), descripcion=descripcion)


def reserva_propia(db: Session, reserva_id: int, u: UsuarioToken) -> Reserva:
    r = db.get(Reserva, reserva_id)
    if not r or r.usuario_id != u.id:
        raise HTTPException(404, "Reserva no encontrada")
    return r


# ---------------------------------------------------------------- usuario
@router.post("/reservas/{reserva_id}/confirmar-llegada", tags=["llegada"])
def confirmar_llegada(reserva_id: int, u: UsuarioToken = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Disponible desde 10 min antes hasta 20 min después del inicio."""
    r = reserva_propia(db, reserva_id, u)
    ahora = reloj.ahora()
    if r.llegada_confirmada_en:
        return {"mensaje": "Tu llegada ya estaba confirmada", "confirmada_en": r.llegada_confirmada_en}
    if r.estado != "confirmada":
        raise HTTPException(409, f"La reserva está {r.estado}")
    desde, hasta = r.inicio_dt - M(config.RECORDATORIO_ANTES), r.inicio_dt + M(config.LIMITE_CONFIRMACION)
    if ahora < desde:
        raise HTTPException(409, f"Podrás confirmar tu llegada desde las {desde:%H:%M} del {r.fecha:%d/%m}")
    if ahora > hasta:
        raise HTTPException(409, "El tiempo para confirmar la llegada ya terminó")
    r.llegada_confirmada_en = ahora
    db.commit()
    return {"mensaje": "¡Llegada confirmada! Disfruta el espacio.", "confirmada_en": ahora}


@router.post("/reservas/{reserva_id}/reportar-ocupado", response_model=ReporteOut, status_code=201, tags=["reportes"])
def reportar_ocupado(reserva_id: int, datos: ReporteIn, u: UsuarioToken = Depends(usuario_actual),
                     db: Session = Depends(get_db)):
    """El titular reporta que la reserva inmediatamente anterior no entregó el espacio pasados 10 minutos."""
    r = reserva_propia(db, reserva_id, u)
    ahora = reloj.ahora()
    if r.estado != "confirmada":
        raise HTTPException(409, f"La reserva está {r.estado}")
    habilitado = r.inicio_dt + M(config.TOLERANCIA_ENTREGA)
    if ahora < habilitado:
        raise HTTPException(409, f"El ocupante anterior tiene {config.TOLERANCIA_ENTREGA} minutos de tolerancia. "
                                 f"Podrás reportar desde las {habilitado:%H:%M}.")
    if ahora > r.fin_dt:
        raise HTTPException(409, "Tu reserva ya terminó")
    if db.scalar(select(Reporte).where(Reporte.reserva_id == r.id)):
        raise HTTPException(409, "Ya reportaste esta situación")
    anterior = db.scalar(select(Reserva).where(
        Reserva.espacio_id == r.espacio_id, Reserva.fecha == r.fecha, Reserva.hora_fin == r.hora_inicio,
        Reserva.estado == "confirmada"))
    if not anterior:
        raise HTTPException(409, "No hay una reserva inmediatamente anterior a la tuya en este espacio. "
                                 "Si el espacio está ocupado por otra razón, contacta a soporte.")
    if anterior.usuario_id == u.id:
        raise HTTPException(409, "La reserva anterior también es tuya")
    s = sanciones.aplicar(db, usuario_id=anterior.usuario_id, email=anterior.usuario_email,
                          nombre=anterior.usuario_nombre, tipo="ocupacion", reserva_id=anterior.id, ahora=ahora,
                          motivo=f"No entregaste {r.espacio.nombre} a las {r.hora_inicio:%H:%M} del {r.fecha:%d/%m} "
                                 f"(reportado por la siguiente reserva tras {config.TOLERANCIA_ENTREGA} min de tolerancia).")
    rep = Reporte(reserva_id=r.id, reportante_id=u.id, reportante_nombre=u.nombre, reserva_reportada_id=anterior.id,
                  reportado_id=anterior.usuario_id, reportado_nombre=anterior.usuario_nombre,
                  reportado_email=anterior.usuario_email, espacio=r.espacio.nombre, comentario=datos.comentario,
                  sancion_id=s.id, creado_en=ahora)
    db.add(rep)
    r.llegada_confirmada_en = r.llegada_confirmada_en or ahora  # quien reporta está en el lugar
    db.commit()
    db.refresh(rep)
    publicador.publicar("reporte.registrado", {
        "usuario_id": u.id, "usuario_email": u.email, "usuario_nombre": u.nombre, "espacio": r.espacio.nombre,
        "fecha": r.fecha.isoformat(), "hora_inicio": r.hora_inicio.strftime("%H:%M"),
        "hora_fin": r.hora_fin.strftime("%H:%M")})
    return rep


@router.get("/sanciones/mias", response_model=list[SancionOut], tags=["sanciones"])
def mis_sanciones(u: UsuarioToken = Depends(usuario_actual), db: Session = Depends(get_db)):
    ahora = reloj.ahora()
    return [sancion_out(s, ahora) for s in db.scalars(select(Sancion).where(Sancion.usuario_id == u.id)
                                                     .order_by(Sancion.id.desc())).all()]


# ---------------------------------------------------------------- administración
@router.get("/admin/usuarios/resumen", tags=["admin"])
def resumen_usuarios(_: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    """Indicadores por usuario (para la tabla de gestión de usuarios)."""
    ahora = reloj.ahora()
    hoy = ahora.date()
    salida: dict[int, dict] = {}

    def fila(uid):
        return salida.setdefault(uid, {"reservas": 0, "activas": 0, "inasistencias": 0, "reportes_recibidos": 0,
                                       "sanciones": 0, "sancion_activa": None})
    for uid, estado, fecha, n in db.execute(select(Reserva.usuario_id, Reserva.estado, Reserva.fecha >= hoy,
                                                   func.count(Reserva.id))
                                            .group_by(Reserva.usuario_id, Reserva.estado, Reserva.fecha >= hoy)).all():
        f = fila(uid)
        f["reservas"] += n
        if estado == "confirmada" and fecha:
            f["activas"] += n
        if estado == "inasistencia":
            f["inasistencias"] += n
    for uid, n in db.execute(select(Reporte.reportado_id, func.count(Reporte.id)).where(Reporte.estado == "valido")
                             .group_by(Reporte.reportado_id)).all():
        fila(uid)["reportes_recibidos"] = n
    for s in db.scalars(select(Sancion).where(Sancion.estado != "anulada")).all():
        f = fila(s.usuario_id)
        f["sanciones"] += 1
        if s.activa(ahora):
            actual = f["sancion_activa"]
            if not actual or s.hasta is None or (actual["hasta"] and s.hasta.isoformat() > actual["hasta"]):
                f["sancion_activa"] = {"id": s.id, "nivel": s.nivel, "hasta": s.hasta.isoformat() if s.hasta else None}
    return {str(k): v for k, v in salida.items()}


@router.get("/admin/usuarios/{uid}/historial", tags=["admin"])
def historial_usuario(uid: int, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    from .main import a_salida  # evitar import circular
    ahora = reloj.ahora()
    reservas = db.scalars(select(Reserva).where(Reserva.usuario_id == uid)
                          .order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc())).all()
    return {
        "reservas": [a_salida(r) for r in reservas],
        "sanciones": [sancion_out(s, ahora) for s in db.scalars(select(Sancion).where(Sancion.usuario_id == uid)
                                                                .order_by(Sancion.id.desc())).all()],
        "reportes_recibidos": [ReporteOut.model_validate(x) for x in db.scalars(
            select(Reporte).where(Reporte.reportado_id == uid).order_by(Reporte.id.desc())).all()],
        "reportes_hechos": [ReporteOut.model_validate(x) for x in db.scalars(
            select(Reporte).where(Reporte.reportante_id == uid).order_by(Reporte.id.desc())).all()],
    }


@router.get("/admin/sanciones", response_model=list[SancionOut], tags=["admin"])
def listar_sanciones(solo_activas: bool = False, _: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    ahora = reloj.ahora()
    todas = [sancion_out(s, ahora) for s in db.scalars(select(Sancion).order_by(Sancion.id.desc())).all()]
    return [s for s in todas if s.activa] if solo_activas else todas


@router.post("/admin/sanciones", response_model=SancionOut, status_code=201, tags=["admin"])
def sancion_manual(datos: SancionManualIn, admin: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    s = sanciones.aplicar(db, usuario_id=datos.usuario_id, email=datos.usuario_email, nombre=datos.usuario_nombre,
                          tipo="manual", motivo=datos.motivo, dias=datos.dias, ahora=reloj.ahora(),
                          creada_por=admin.nombre)
    return sancion_out(s, reloj.ahora())


@router.post("/admin/sanciones/{sid}/levantar", response_model=SancionOut, tags=["admin"])
def levantar_sancion(sid: int, datos: NotaIn, admin: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    """Termina la sanción antes de tiempo (sigue contando para la reincidencia)."""
    s = db.get(Sancion, sid)
    if not s:
        raise HTTPException(404, "Sanción no encontrada")
    if s.estado != "vigente":
        raise HTTPException(409, f"La sanción ya está {s.estado}")
    s.estado = "levantada"
    s.nota_admin = f"{datos.nota} — {admin.nombre}"
    db.commit()
    publicador.publicar("sancion.levantada", {**sanciones.evento_sancion(s), "nota": datos.nota})
    return sancion_out(s, reloj.ahora())


@router.get("/admin/reportes", response_model=list[ReporteOut], tags=["admin"])
def listar_reportes(_: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    return db.scalars(select(Reporte).order_by(Reporte.id.desc())).all()


@router.post("/admin/reportes/{rid}/anular", response_model=ReporteOut, tags=["admin"])
def anular_reporte(rid: int, datos: NotaIn, admin: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    """Reporte inválido: se anula junto con su sanción, que deja de contar para la reincidencia."""
    rep = db.get(Reporte, rid)
    if not rep:
        raise HTTPException(404, "Reporte no encontrado")
    if rep.estado == "anulado":
        raise HTTPException(409, "El reporte ya estaba anulado")
    rep.estado = "anulado"
    s = db.get(Sancion, rep.sancion_id) if rep.sancion_id else None
    if s and s.estado != "anulada":
        s.estado = "anulada"
        s.nota_admin = f"Reporte anulado: {datos.nota} — {admin.nombre}"
        db.commit()
        publicador.publicar("sancion.levantada", {**sanciones.evento_sancion(s), "nota": "El reporte fue anulado "
                                                                                        "por la administración."})
    db.commit()
    return rep


@router.post("/tareas/ejecutar", tags=["sistema"])
def ejecutar_tareas(x_tareas_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Ejecuta el programador una vez (para un cron externo). Requiere el encabezado X-Tareas-Token."""
    if not config.TAREAS_TOKEN or x_tareas_token != config.TAREAS_TOKEN:
        raise HTTPException(403, "Token de tareas inválido")
    from .tareas import procesar
    return procesar(db)
