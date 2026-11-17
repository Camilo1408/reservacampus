from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, index=True)
    email: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(40))
    titulo: Mapped[str] = mapped_column(String(120))
    mensaje: Mapped[str] = mapped_column(String(500))
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    correo_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    evento_id: Mapped[str] = mapped_column(String(40), unique=True)  # idempotencia
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
