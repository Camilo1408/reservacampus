from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TipoEspacio = Literal["sala_estudio", "laboratorio", "auditorio", "cancha"]


class EspacioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    tipo: TipoEspacio
    capacidad: int = Field(ge=1, le=1000)
    ubicacion: str = Field(min_length=2, max_length=120)
    descripcion: str = Field(default="", max_length=300)
    hora_apertura: time = time(7, 0)
    hora_cierre: time = time(21, 0)
    activo: bool = True


class EspacioOut(EspacioIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ReservaIn(BaseModel):
    espacio_id: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    asistentes: int = Field(default=1, ge=1, le=1000)
    motivo: str = Field(default="", max_length=200)

    @field_validator("motivo")
    @classmethod
    def limpiar(cls, v: str) -> str:
        return v.replace("<", "").replace(">", "").strip()


class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    espacio_id: int
    espacio_nombre: str
    usuario_id: int
    usuario_nombre: str
    usuario_email: str
    fecha: date
    hora_inicio: time
    hora_fin: time
    asistentes: int
    motivo: str
    estado: str
    creada_en: datetime


class Franja(BaseModel):
    hora_inicio: time
    hora_fin: time


class DisponibilidadOut(BaseModel):
    espacio: EspacioOut
    fecha: date
    libre: bool
    ocupado: list[Franja]
