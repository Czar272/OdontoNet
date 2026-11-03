"""Plan de tratamiento y seguimiento (ODON-158)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, constr, validator

from app.models.treatment import TreatmentStatus, is_valid_tooth

Notes = constr(strip_whitespace=True, max_length=2000)
Procedure = constr(strip_whitespace=True, min_length=1, max_length=300)


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

    _tooth = validator("tooth", allow_reuse=True)(_check_tooth)
    _blank_notes = validator("notes", pre=True, allow_reuse=True)(_blank_to_none)


class TreatmentUpdate(BaseModel):
    """Edición parcial: solo se cambian los campos enviados."""

    procedure: Optional[Procedure] = None
    tooth: Optional[int] = None
    notes: Optional[Notes] = None
    planned_date: Optional[date] = None
    proposed_visit_id: Optional[int] = None

    _tooth = validator("tooth", allow_reuse=True)(_check_tooth)
    _blank_notes = validator("notes", pre=True, allow_reuse=True)(_blank_to_none)


class TreatmentStatusUpdate(BaseModel):
    status: TreatmentStatus
    # Obligatorio para cancelar.
    reason: Optional[constr(strip_whitespace=True, max_length=500)] = None
    # Obligatoria para completar: consulta en que se realizó.
    completed_visit_id: Optional[int] = None

    _blank_reason = validator("reason", pre=True, allow_reuse=True)(_blank_to_none)


class PersonRef(BaseModel):
    id: int
    name: str


class VisitRef(BaseModel):
    id: int
    visit_at: datetime
    reason: str
    voided: bool


class TreatmentResponse(BaseModel):
    id: int
    patient_id: int
    procedure: str
    tooth: Optional[int]
    notes: Optional[str]
    planned_date: Optional[date]
    status: TreatmentStatus
    # Motivo del último cambio de estado (p. ej. por qué se canceló).
    status_reason: Optional[str]
    status_changed_at: datetime
    proposed_visit: Optional[VisitRef]
    completed_visit: Optional[VisitRef]
    created_by: PersonRef
    created_at: datetime
    updated_by: PersonRef
    updated_at: datetime


class TreatmentStatusChangeResponse(BaseModel):
    from_status: Optional[TreatmentStatus]
    to_status: TreatmentStatus
    reason: Optional[str]
    changed_by: PersonRef
    changed_at: datetime
