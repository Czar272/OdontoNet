"""Consultas clínicas (ODON-154)."""
from datetime import date, datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.fields import DateTime

LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


def _blank_to_none(value):
    return None if isinstance(value, str) and value == "" else value


class VisitContent(BaseModel):
    """Contenido clínico completo; se envía entero al crear y al editar."""

    visit_at: DateTime
    doctor_id: int
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    findings: Optional[LongText] = None
    diagnosis: Optional[LongText] = None
    procedures: Optional[LongText] = None
    instructions: Optional[LongText] = None
    next_visit_date: Optional[date] = None

    _blank_texts = field_validator(
        "findings", "diagnosis", "procedures", "instructions", mode="before"
    )(lambda value: _blank_to_none(value.strip() if isinstance(value, str) else value))

    @field_validator("visit_at")
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Indica la zona horaria de la fecha de atención.")
        return value


class VisitCreate(VisitContent):
    pass


class VisitUpdate(VisitContent):
    # Revisión que se estaba editando: si otra persona guardó antes, 409.
    base_revision: Annotated[int, Field(ge=1)]


class VisitVoid(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class PersonRef(BaseModel):
    id: int
    name: str


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    revision: int
    visit_at: DateTime
    doctor: PersonRef
    reason: str
    findings: Optional[str] = None
    diagnosis: Optional[str] = None
    procedures: Optional[str] = None
    instructions: Optional[str] = None
    next_visit_date: Optional[date] = None
    created_by: PersonRef
    created_at: DateTime
    # Último guardado (alta o edición).
    updated_by: PersonRef
    updated_at: DateTime
    voided_at: Optional[DateTime] = None
    voided_by: Optional[PersonRef] = None
    void_reason: Optional[str] = None


class VisitRevisionResponse(BaseModel):
    revision: int
    edited_by: PersonRef
    edited_at: DateTime
    visit_at: DateTime
    doctor: PersonRef
    reason: str
    findings: Optional[str] = None
    diagnosis: Optional[str] = None
    procedures: Optional[str] = None
    instructions: Optional[str] = None
    next_visit_date: Optional[date] = None
