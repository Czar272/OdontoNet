"""Plan de tratamiento y seguimiento (ODON-158)."""
from datetime import date
from typing import Annotated, Optional

from pydantic import BaseModel, StringConstraints, field_validator

from app.models.treatment import TreatmentStatus, is_valid_tooth
from app.schemas.fields import DateTime

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Procedure = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


def _check_tooth(value: Optional[int]) -> Optional[int]:
    if value is not None and not is_valid_tooth(value):
        raise ValueError("Pieza dental inválida: usa la numeración FDI (11–48 o 51–85).")
    return value


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class TreatmentCreate(BaseModel):
    procedure: Procedure
    tooth: Optional[int] = None
    notes: Optional[Notes] = None
    planned_date: Optional[date] = None
    # Consulta en que se indicó (opcional).
    proposed_visit_id: Optional[int] = None

    _tooth = field_validator("tooth")(_check_tooth)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)


class TreatmentUpdate(BaseModel):
    """Edición parcial: solo se cambian los campos enviados."""

    procedure: Optional[Procedure] = None
    tooth: Optional[int] = None
    notes: Optional[Notes] = None
    planned_date: Optional[date] = None
    proposed_visit_id: Optional[int] = None

    _tooth = field_validator("tooth")(_check_tooth)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)


class TreatmentStatusUpdate(BaseModel):
    status: TreatmentStatus
    # Obligatorio para cancelar.
    reason: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None
    # Obligatoria para completar: consulta en que se realizó.
    completed_visit_id: Optional[int] = None

    _blank_reason = field_validator("reason", mode="before")(_blank_to_none)


class PersonRef(BaseModel):
    id: int
    name: str


class VisitRef(BaseModel):
    id: int
    visit_at: DateTime
    reason: str
    voided: bool


class TreatmentResponse(BaseModel):
    id: int
    patient_id: int
    procedure: str
    tooth: Optional[int] = None
    notes: Optional[str] = None
    planned_date: Optional[date] = None
    status: TreatmentStatus
    # Motivo del último cambio de estado (p. ej. por qué se canceló).
    status_reason: Optional[str] = None
    status_changed_at: DateTime
    proposed_visit: Optional[VisitRef] = None
    completed_visit: Optional[VisitRef] = None
    created_by: PersonRef
    created_at: DateTime
    updated_by: PersonRef
    updated_at: DateTime


class TreatmentStatusChangeResponse(BaseModel):
    from_status: Optional[TreatmentStatus] = None
    to_status: TreatmentStatus
    reason: Optional[str] = None
    changed_by: PersonRef
    changed_at: DateTime
