"""Historial cronológico del paciente (ODON-162)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

EventType = Literal["visit", "treatment", "medical_history", "appointment", "image", "periodontal"]


class PersonRef(BaseModel):
    id: int
    name: str


class TimelineEvent(BaseModel):
    # Estable y único en la línea de tiempo: "<tipo>.<acción>:<id de origen>".
    id: str
    type: EventType
    # visit: attended | edited | voided · treatment: proposed | accepted | in_progress |
    # completed | cancelled · medical_history: version · appointment: completed | no_show
    # · image: uploaded | edited | voided
    action: str
    occurred_at: datetime
    title: str
    detail: Optional[str]
    # Doctor que atendió (consultas y citas) o usuario que hizo el cambio.
    actor: Optional[PersonRef]
    # id de la consulta, tratamiento, cita o imagen; número de versión en la historia médica.
    ref_id: int
    # La consulta o la fotografía de este evento está anulada.
    voided: bool


class TimelinePage(BaseModel):
    items: list[TimelineEvent]
    # null cuando no hay más eventos.
    next_cursor: Optional[str]
