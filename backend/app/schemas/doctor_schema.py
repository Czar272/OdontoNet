from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.schemas.user_schema import UserResponse

Specialization = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
LicenseNumber = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]


class _DoctorProfileFields(BaseModel):
    specialization: Optional[Specialization] = None
    license_number: Optional[LicenseNumber] = None
    phone: Optional[Phone] = None

    @field_validator("specialization", "license_number", "phone", mode="before")
    def empty_string_to_none(cls, value):
        # Los formularios envían "" en campos opcionales vacíos.
        if isinstance(value, str) and not value.strip():
            return None
        return value


class DoctorCreate(_DoctorProfileFields):
    """Perfil clínico para un usuario con rol doctor de la misma clínica."""

    user_id: int


class DoctorUpdate(_DoctorProfileFields):
    """Edición parcial del perfil clínico. El usuario y la clínica no cambian;
    nombre, correo y estado se gestionan en /users."""


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    specialization: str | None = None
    license_number: str | None = None
    phone: str | None = None
    user: UserResponse
    clinic_id: int

    model_config = ConfigDict(from_attributes=True)
