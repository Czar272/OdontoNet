"""Imágenes clínicas y consentimiento para fotografías (ODON-8)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, constr, validator


class PersonRef(BaseModel):
    id: int
    name: str


class VisitRef(BaseModel):
    id: int
    visit_at: datetime
    reason: str
    voided: bool


class PhotoConsentCreate(BaseModel):
    """Versión nueva del consentimiento. Revocar es enviar granted = false."""

    granted: bool
    # Solo si el formulario firmado lo autoriza expresamente.
    research_use: bool = False
    # Fecha del documento (firma o revocación).
    signed_on: date
    notes: Optional[constr(strip_whitespace=True, max_length=500)] = None

    @validator("notes", pre=True)
    def _blank_notes(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("research_use")
    def _research_requires_grant(cls, value, values):
        if value and not values.get("granted"):
            raise ValueError("El uso en investigación requiere autorizar las fotografías clínicas.")
        return value


class PhotoConsentResponse(BaseModel):
    id: int
    version: int
    granted: bool
    research_use: bool
    signed_on: date
    notes: Optional[str]
    recorded_by: PersonRef
    recorded_at: datetime


class PhotoConsentStatus(BaseModel):
    """Versión vigente (o null si nunca se registró) e historial, la más reciente primero."""

    current: Optional[PhotoConsentResponse]
    history: list[PhotoConsentResponse]


class PatientImageResponse(BaseModel):
    id: int
    patient_id: int
    clinical_visit: Optional[VisitRef]
    tooth: Optional[int]
    content_type: str
    size_bytes: int
    width: int
    height: int
    consent_id: int
    uploaded_by: PersonRef
    uploaded_at: datetime
