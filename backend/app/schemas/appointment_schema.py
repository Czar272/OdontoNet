from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.appointment import MAX_DURATION_MINUTES, MIN_DURATION_MINUTES, AppointmentStatus
from app.schemas.doctor_schema import DoctorResponse
from app.schemas.fields import DateTime

DurationMinutes = Annotated[int, Field(ge=MIN_DURATION_MINUTES, le=MAX_DURATION_MINUTES)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]

DEFAULT_DURATION_MINUTES = 30


def _validate_starts_at(value: datetime | None) -> datetime | None:
    """Inicio con zona horaria y exacto al minuto ("2026-11-03T09:30:00-06:00")."""
    if value is None:
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha y hora deben incluir la zona horaria.")
    if value.second or value.microsecond:
        raise ValueError("La hora debe ser exacta al minuto.")
    return value


def _empty_to_none(value):
    # Los formularios envían "" en campos opcionales vacíos.
    if isinstance(value, str) and not value.strip():
        return None
    return value


class AppointmentCreate(BaseModel):
    """Alta de cita (ODON-133). clinic_id, estado y autor no forman parte del
    contrato: los asigna el backend (clínica del token, «Programada», usuario
    de la sesión)."""

    patient_id: int
    doctor_id: int
    starts_at: DateTime
    duration_minutes: DurationMinutes = DEFAULT_DURATION_MINUTES
    reason: Optional[Reason] = None
    # Confirmación explícita para agendar fuera del horario del doctor (ODON-142).
    allow_outside_schedule: bool = False

    _starts_at = field_validator("starts_at")(_validate_starts_at)
    _reason = field_validator("reason", mode="before")(_empty_to_none)


class AppointmentUpdate(BaseModel):
    """Reprogramación parcial: doctor, horario, duración o motivo. El paciente
    no cambia (se crea otra cita) y el estado se gestiona en ODON-146."""

    doctor_id: Optional[int] = None
    starts_at: Optional[DateTime] = None
    duration_minutes: Optional[DurationMinutes] = None
    reason: Optional[Reason] = None
    allow_outside_schedule: bool = False

    _starts_at = field_validator("starts_at")(_validate_starts_at)
    _reason = field_validator("reason", mode="before")(_empty_to_none)


class AppointmentPatient(BaseModel):
    """Datos mínimos del paciente para la agenda. Incluye el teléfono para
    llamar a confirmar (ODON-146); nada clínico."""

    id: int
    first_name: str
    last_name: str
    phone: str | None = None
    archived_at: DateTime | None = None

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    id: int
    clinic_id: int
    patient_id: int
    doctor_id: int
    starts_at: DateTime
    ends_at: DateTime
    duration_minutes: int
    status: AppointmentStatus
    reason: str | None = None
    created_by_user_id: int
    created_at: DateTime
    updated_at: DateTime
    patient: AppointmentPatient
    doctor: DoctorResponse

    model_config = ConfigDict(from_attributes=True)


Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]


class AppointmentStatusUpdate(BaseModel):
    """Cambio de estado (ODON-147) con nota opcional del seguimiento."""

    status: AppointmentStatus
    note: Optional[Note] = None

    _note = field_validator("note", mode="before")(_empty_to_none)


class StatusChangeUser(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentStatusChangeResponse(BaseModel):
    id: int
    from_status: AppointmentStatus | None = None
    to_status: AppointmentStatus
    note: str | None = None
    changed_at: DateTime
    changed_by: StatusChangeUser

    model_config = ConfigDict(from_attributes=True)
