"""Auditoría de cambios y exportaciones (ODON-222)."""
from typing import Optional

from pydantic import BaseModel

from app.schemas.fields import DateTime


class AuditActor(BaseModel):
    id: int
    name: str
    role: str


class AuditEventRead(BaseModel):
    id: int
    occurred_at: DateTime
    actor: AuditActor
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    patient_id: Optional[int] = None
    # Nombres de los campos cambiados; nunca sus valores.
    fields: list[str]


class AuditPage(BaseModel):
    items: list[AuditEventRead]
    next_cursor: Optional[str] = None
