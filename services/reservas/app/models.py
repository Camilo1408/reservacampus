from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Espacio(Base):
    __tablename__ = "espacios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    tipo: Mapped[str] = mapped_column(String(30))  # sala_estudio | laboratorio | auditorio | cancha
    capacidad: Mapped[int] = mapped_column(Integer)
    ubicacion: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    hora_apertura: Mapped[time] = mapped_column(Time, default=time(7, 0))
    hora_cierre: Mapped[time] = mapped_column(Time, default=time(21, 0))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="espacio")


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (Index("ix_reserva_espacio_fecha", "espacio_id", "fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    espacio_id: Mapped[int] = mapped_column(ForeignKey("espacios.id"))
    usuario_id: Mapped[int] = mapped_column(Integer, index=True)  # id del auth-service (sin FK: otra BD)
    usuario_email: Mapped[str] = mapped_column(String(120))
    usuario_nombre: Mapped[str] = mapped_column(String(80))
    fecha: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    asistentes: Mapped[int] = mapped_column(Integer, default=1)
    motivo: Mapped[str] = mapped_column(String(200), default="")
    estado: Mapped[str] = mapped_column(String(20), default="confirmada")  # confirmada | cancelada
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    espacio: Mapped[Espacio] = relationship(back_populates="reservas")
