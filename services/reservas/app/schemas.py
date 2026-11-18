from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TipoEspacio = Literal["sala_estudio", "laboratorio", "auditorio", "cancha", "recreacion"]


def _limpiar(v: str) -> str:
    return v.replace("<", "").replace(">", "").strip()


class EspacioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    tipo: TipoEspacio
    capacidad: int = Field(ge=1, le=1000)
    ubicacion: str = Field(min_length=2, max_length=120)
    descripcion: str = Field(default="", max_length=300)
    actividades: str = Field(default="", max_length=300)
    hora_apertura: time = time(7, 0)
    hora_cierre: time = time(21, 0)
    activo: bool = True

    limpiar_texto = field_validator("nombre", "ubicacion", "descripcion", "actividades")(classmethod(lambda cls, v: _limpiar(v)))

    @model_validator(mode="after")
    def horario_valido(self):
        if self.hora_apertura >= self.hora_cierre:
            raise ValueError("La hora de cierre debe ser posterior a la de apertura")
        return self


class EspacioOut(EspacioIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class EstadoEspacioIn(BaseModel):
    activo: bool


class ReservaIn(BaseModel):
    espacio_id: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    asistentes: int = Field(default=1, ge=1, le=1000)
    motivo: str = Field(default="", max_length=200)

    limpiar_texto = field_validator("motivo")(classmethod(lambda cls, v: _limpiar(v)))


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
    motivo_revocacion: str | None = None
    llegada_confirmada_en: datetime | None = None
    creada_en: datetime


class RevocarIn(BaseModel):
    justificacion: str = Field(min_length=10, max_length=300)

    limpiar_texto = field_validator("justificacion")(classmethod(lambda cls, v: _limpiar(v)))


class HorarioIn(BaseModel):
    espacio_id: int
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fin: time
    materia: str = Field(min_length=2, max_length=100)
    docente: str = Field(default="", max_length=80)
    vigente_desde: date | None = None
    vigente_hasta: date | None = None

    limpiar_texto = field_validator("materia", "docente")(classmethod(lambda cls, v: _limpiar(v)))

    @model_validator(mode="after")
    def validar(self):
        if self.hora_inicio >= self.hora_fin:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        if self.vigente_desde and self.vigente_hasta and self.vigente_desde > self.vigente_hasta:
            raise ValueError("La vigencia es inválida")
        return self


class HorarioOut(HorarioIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    espacio_nombre: str = ""


class FilaCargaHorario(BaseModel):
    """Fila del CSV: el espacio se identifica por nombre o id y el día por nombre o número."""
    espacio: str
    dia: str
    hora_inicio: str
    hora_fin: str
    materia: str
    docente: str = ""


class CargaHorariosIn(BaseModel):
    filas: list[FilaCargaHorario] = Field(min_length=1, max_length=1000)
    reemplazar: bool = False
    vigente_desde: date | None = None
    vigente_hasta: date | None = None


class ConflictoOut(BaseModel):
    reserva_id: int
    espacio: str
    fecha: date
    hora_inicio: time
    hora_fin: time
    usuario_nombre: str


class ResultadoCarga(BaseModel):
    creados: int
    errores: list[str]
    conflictos: list[ConflictoOut]


class Franja(BaseModel):
    hora_inicio: time
    hora_fin: time
    tipo: Literal["reserva", "clase"] = "reserva"
    etiqueta: str = ""


class DisponibilidadOut(BaseModel):
    espacio: EspacioOut
    fecha: date
    libre: bool
    ocupado: list[Franja]
