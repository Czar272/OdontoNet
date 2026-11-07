"""Imágenes clínicas y consentimiento para fotografías (ODON-8)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, constr, validator

from app.models.treatment import is_valid_tooth

Origin = Literal["intraoral_camera", "phone", "camera", "external"]
View = Literal["frontal", "right_lateral", "left_lateral", "upper_occlusal", "lower_occlusal", "detail", "other"]


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


class PatientImageUpdate(BaseModel):
    """Corrección de metadatos (ODON-178): se envían completos. El archivo no cambia."""

    base_revision: int
    origin: Origin
    view: Optional[View] = None
    taken_on: Optional[date] = None
    clinical_visit_id: Optional[int] = None
    tooth: Optional[int] = None

    @validator("tooth")
    def _valid_tooth(cls, value):
        if value is not None and not is_valid_tooth(value):
            raise ValueError("Pieza dental inválida: usa la numeración FDI (11–48 o 51–85).")
        return value


class ImageVoid(BaseModel):
    reason: constr(strip_whitespace=True, min_length=1, max_length=500)


class PatientImageRevisionResponse(BaseModel):
    revision: int
    origin: Optional[str]
    view: Optional[str]
    taken_on: Optional[date]
    clinical_visit_id: Optional[int]
    tooth: Optional[int]
    edited_by: PersonRef
    edited_at: datetime


class ImageAccessResponse(BaseModel):
    user: PersonRef
    accessed_at: datetime


class PatientImageResponse(BaseModel):
    id: int
    patient_id: int
    clinical_visit: Optional[VisitRef]
    tooth: Optional[int]
    # null en imágenes anteriores a ODON-178 («sin registrar»).
    origin: Optional[str]
    view: Optional[str]
    taken_on: Optional[date]
    revision: int
    content_type: str
    size_bytes: int
    width: int
    height: int
    consent_id: int
    uploaded_by: PersonRef
    uploaded_at: datetime
    voided_at: Optional[datetime]
    voided_by: Optional[PersonRef]
    void_reason: Optional[str]
