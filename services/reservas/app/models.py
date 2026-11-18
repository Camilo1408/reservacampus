from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Espacio(Base):
    __tablename__ = "espacios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    tipo: Mapped[str] = mapped_column(String(30))  # sala_estudio | laboratorio | auditorio | cancha | recreacion
    capacidad: Mapped[int] = mapped_column(Integer)
    ubicacion: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    # Actividades permitidas, separadas por coma (p. ej. "videojuegos, juegos de mesa"). Las usa el chatbot.
    actividades: Mapped[str] = mapped_column(String(300), default="")
    hora_apertura: Mapped[time] = mapped_column(Time, default=time(7, 0))
    hora_cierre: Mapped[time] = mapped_column(Time, default=time(21, 0))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="espacio")
    horarios: Mapped[list["HorarioClase"]] = relationship(back_populates="espacio", cascade="all, delete-orphan")


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (Index("ix_reserva_espacio_fecha", "espacio_id", "fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    espacio_id: Mapped[int] = mapped_column(ForeignKey("espacios.id", ondelete="CASCADE"))
    usuario_id: Mapped[int] = mapped_column(Integer, index=True)  # id del auth-service (sin FK: otra BD)
    usuario_email: Mapped[str] = mapped_column(String(120))
    usuario_nombre: Mapped[str] = mapped_column(String(80))
    fecha: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    asistentes: Mapped[int] = mapped_column(Integer, default=1)
    motivo: Mapped[str] = mapped_column(String(200), default="")
    # confirmada | cancelada | revocada | inasistencia
    estado: Mapped[str] = mapped_column(String(20), default="confirmada")
    motivo_revocacion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Confirmación de llegada (hora local) y avisos ya enviados (idempotencia del programador)
    llegada_confirmada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    aviso_previo: Mapped[bool] = mapped_column(Boolean, default=False)
    aviso_inicio: Mapped[bool] = mapped_column(Boolean, default=False)
    aviso_final: Mapped[bool] = mapped_column(Boolean, default=False)

    espacio: Mapped[Espacio] = relationship(back_populates="reservas")

    @property
    def inicio_dt(self) -> datetime:
        return datetime.combine(self.fecha, self.hora_inicio)

    @property
    def fin_dt(self) -> datetime:
        return datetime.combine(self.fecha, self.hora_fin)


class Sancion(Base):
    """Restricción para reservar. Nivel 1: día siguiente · 2: 3 días · 3: 7 días · 4: suspensión indefinida."""
    __tablename__ = "sanciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, index=True)
    usuario_email: Mapped[str] = mapped_column(String(120))
    usuario_nombre: Mapped[str] = mapped_column(String(80))
    nivel: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20))  # ocupacion | inasistencia | manual
    motivo: Mapped[str] = mapped_column(String(300))
    reserva_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desde: Mapped[datetime] = mapped_column(DateTime)
    hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # None = hasta que el admin la levante
    estado: Mapped[str] = mapped_column(String(20), default="vigente")  # vigente | levantada | anulada
    nota_admin: Mapped[str | None] = mapped_column(String(300), nullable=True)
    creada_por: Mapped[str] = mapped_column(String(80), default="sistema")
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def activa(self, ahora: datetime) -> bool:
        return self.estado == "vigente" and (self.hasta is None or self.hasta > ahora)


class Reporte(Base):
    """Reporte de un usuario porque el ocupante anterior no entregó el espacio a tiempo."""
    __tablename__ = "reportes"

    id: Mapped[int] = mapped_column(primary_key=True)
    reserva_id: Mapped[int] = mapped_column(Integer, unique=True)  # reserva de quien reporta
    reportante_id: Mapped[int] = mapped_column(Integer, index=True)
    reportante_nombre: Mapped[str] = mapped_column(String(80))
    reserva_reportada_id: Mapped[int] = mapped_column(Integer)
    reportado_id: Mapped[int] = mapped_column(Integer, index=True)
    reportado_nombre: Mapped[str] = mapped_column(String(80))
    reportado_email: Mapped[str] = mapped_column(String(120))
    espacio: Mapped[str] = mapped_column(String(80))
    comentario: Mapped[str] = mapped_column(String(300), default="")
    estado: Mapped[str] = mapped_column(String(20), default="valido")  # valido | anulado
    sancion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now())


class HorarioClase(Base):
    """Bloque fijo semanal (clase) en el que el espacio no se puede reservar."""
    __tablename__ = "horarios_clase"
    __table_args__ = (Index("ix_horario_espacio_dia", "espacio_id", "dia_semana"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    espacio_id: Mapped[int] = mapped_column(ForeignKey("espacios.id", ondelete="CASCADE"))
    dia_semana: Mapped[int] = mapped_column(Integer)  # 0 = lunes ... 6 = domingo
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    materia: Mapped[str] = mapped_column(String(100))
    docente: Mapped[str] = mapped_column(String(80), default="")
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)

    espacio: Mapped[Espacio] = relationship(back_populates="horarios")

    def aplica(self, fecha: date) -> bool:
        return (fecha.weekday() == self.dia_semana
                and (self.vigente_desde is None or fecha >= self.vigente_desde)
                and (self.vigente_hasta is None or fecha <= self.vigente_hasta))
