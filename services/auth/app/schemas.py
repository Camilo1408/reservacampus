import re
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegistroIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü .'-]{2,80}", v):
            raise ValueError("El nombre solo puede contener letras y espacios")
        return v

    @field_validator("password")
    @classmethod
    def password_segura(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contraseña debe tener letras y números")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: EmailStr
    rol: str
    estado: str = "activo"
    motivo_estado: str | None = None
    ultimo_acceso: datetime | None = None
    creado_en: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_min: int
    usuario: UsuarioOut


class EstadoIn(BaseModel):
    estado: Literal["activo", "suspendido", "bloqueado"]
    motivo: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def motivo_obligatorio(self):
        self.motivo = self.motivo.replace("<", "").replace(">", "").strip()
        if self.estado != "activo" and len(self.motivo) < 10:
            raise ValueError("Indica un motivo de al menos 10 caracteres")
        return self


class RolIn(BaseModel):
    rol: Literal["estudiante", "admin"]


class RecuperarIn(BaseModel):
    email: EmailStr


class RestablecerIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_segura(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contraseña debe tener letras y números")
        return v


class CambiarPasswordIn(BaseModel):
    actual: str = Field(min_length=1, max_length=128)
    nueva: str = Field(min_length=8, max_length=128)

    @field_validator("nueva")
    @classmethod
    def password_segura(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("La contraseña debe tener letras y números")
        return v
