"""Consultas clínicas (ODON-154)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, conint, constr, validator

LongText = constr(strip_whitespace=True, max_length=4000)


def _blank_to_none(value):
    return None if isinstance(value, str) and value == "" else value


class VisitContent(BaseModel):
    """Contenido clínico completo; se envía entero al crear y al editar."""

    visit_at: datetime
    doctor_id: int
    reason: constr(strip_whitespace=True, min_length=1, max_length=500)
    findings: Optional[LongText] = None
    diagnosis: Optional[LongText] = None
    procedures: Optional[LongText] = None
    instructions: Optional[LongText] = None
    next_visit_date: Optional[date] = None

    _blank_texts = validator(
        "findings", "diagnosis", "procedures", "instructions", pre=True, allow_reuse=True
    )(lambda value: _blank_to_none(value.strip() if isinstance(value, str) else value))

    @validator("visit_at")
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Indica la zona horaria de la fecha de atención.")
        return value


class VisitCreate(VisitContent):
    pass


class VisitUpdate(VisitContent):
    # Revisión que se estaba editando: si otra persona guardó antes, 409.
    base_revision: conint(ge=1)


class VisitVoid(BaseModel):
    reason: constr(strip_whitespace=True, min_length=1, max_length=500)


class PersonRef(BaseModel):
    id: int
    name: str


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    revision: int
    visit_at: datetime
    doctor: PersonRef
    reason: str
    findings: Optional[str]
    diagnosis: Optional[str]
    procedures: Optional[str]
    instructions: Optional[str]
    next_visit_date: Optional[date]
    created_by: PersonRef
    created_at: datetime
    # Último guardado (alta o edición).
    updated_by: PersonRef
    updated_at: datetime
    voided_at: Optional[datetime]
    voided_by: Optional[PersonRef]
    void_reason: Optional[str]


class VisitRevisionResponse(BaseModel):
    revision: int
    edited_by: PersonRef
    edited_at: datetime
    visit_at: datetime
    doctor: PersonRef
    reason: str
    findings: Optional[str]
    diagnosis: Optional[str]
    procedures: Optional[str]
    instructions: Optional[str]
    next_visit_date: Optional[date]
