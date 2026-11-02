from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, constr, validator

from app.schemas.doctor_schema import DoctorResponse


class PatientCreate(BaseModel):
    """Datos de alta de paciente. clinic_id NO forma parte del contrato:
    se asigna desde la sesión y cualquier valor enviado se ignora."""

    first_name: constr(strip_whitespace=True, min_length=1, max_length=100)
    last_name: constr(strip_whitespace=True, min_length=1, max_length=100)
    birth_date: date | None = None
    phone: constr(strip_whitespace=True, max_length=30) | None = None
    email: EmailStr | None = None
    address: constr(strip_whitespace=True, max_length=255) | None = None
    doctor_id: int | None = None

    @validator("birth_date", "phone", "email", "address", pre=True)
    def empty_string_to_none(cls, value):
        # Los formularios envían "" en campos opcionales vacíos.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("birth_date")
    def birth_date_not_in_future(cls, value):
        if value is not None and value > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return value


class PatientUpdate(BaseModel):
    """Edición parcial (ODON-118). Solo cambian los campos enviados; "" o null
    borra los opcionales y doctor_id null deja al paciente sin doctor.
    clinic_id no forma parte del contrato."""

    first_name: Optional[constr(strip_whitespace=True, min_length=1, max_length=100)] = None
    last_name: Optional[constr(strip_whitespace=True, min_length=1, max_length=100)] = None
    birth_date: Optional[date] = None
    phone: Optional[constr(strip_whitespace=True, max_length=30)] = None
    email: Optional[EmailStr] = None
    address: Optional[constr(strip_whitespace=True, max_length=255)] = None
    doctor_id: Optional[int] = None

    @validator("birth_date", "phone", "email", "address", pre=True)
    def empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("birth_date")
    def birth_date_not_in_future(cls, value):
        if value is not None and value > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return value


class PatientResponse(BaseModel):

    id: int
    first_name: str
    last_name: str
    birth_date: date | None
    phone: str | None
    email: str | None
    address: str | None
    doctor_id: int | None = None
    doctor: DoctorResponse | None
    clinic_id: int
    # null = activo; con fecha = archivado (ODON-122).
    archived_at: datetime | None = None

    class Config:
        orm_mode = True
