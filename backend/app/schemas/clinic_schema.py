from typing import Annotated, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

ClinicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ClinicUpdate(BaseModel):
    """Edición parcial de la clínica del administrador autenticado (ODON-74).

    No incluye id: la clínica siempre es la de la sesión. Enviar "" o null en
    dirección, teléfono o correo borra el dato; el nombre es obligatorio."""

    name: Optional[ClinicName] = None
    address: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]] = None
    phone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]] = None
    email: Optional[EmailStr] = None
    # Zona IANA de la clínica (ODON-142), p. ej. "America/Guatemala".
    timezone: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]] = None

    @field_validator("timezone")
    def valid_timezone(cls, value):
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Zona horaria no válida.")
        return value

    @field_validator("address", "phone", "email", mode="before")
    def empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ClinicResponse(BaseModel):

    id: int
    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    timezone: str

    model_config = ConfigDict(from_attributes=True)


class ClinicSimpleResponse(BaseModel):

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
