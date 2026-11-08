"""Imágenes clínicas y consentimiento para fotografías (ODON-8)."""
from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, StringConstraints, ValidationInfo, field_validator

from app.models.treatment import is_valid_tooth
from app.schemas.fields import DateTime

Origin = Literal["intraoral_camera", "phone", "camera", "external"]
View = Literal["frontal", "right_lateral", "left_lateral", "upper_occlusal", "lower_occlusal", "detail", "other"]


class PersonRef(BaseModel):
    id: int
    name: str


class VisitRef(BaseModel):
    id: int
    visit_at: DateTime
    reason: str
    voided: bool


class PhotoConsentCreate(BaseModel):
    """Versión nueva del consentimiento. Revocar es enviar granted = false."""

    granted: bool
    # Solo si el formulario firmado lo autoriza expresamente.
    research_use: bool = False
    # Fecha del documento (firma o revocación).
    signed_on: date
    notes: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None

    @field_validator("notes", mode="before")
    def _blank_notes(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("research_use")
    def _research_requires_grant(cls, value, info: ValidationInfo):
        if value and not info.data.get("granted"):
            raise ValueError("El uso en investigación requiere autorizar las fotografías clínicas.")
        return value


class PhotoConsentResponse(BaseModel):
    id: int
    version: int
    granted: bool
    research_use: bool
    signed_on: date
    notes: Optional[str] = None
    recorded_by: PersonRef
    recorded_at: DateTime


class PhotoConsentStatus(BaseModel):
    """Versión vigente (o null si nunca se registró) e historial, la más reciente primero."""

    current: Optional[PhotoConsentResponse] = None
    history: list[PhotoConsentResponse]


class PatientImageUpdate(BaseModel):
    """Corrección de metadatos (ODON-178): se envían completos. El archivo no cambia."""

    base_revision: int
    origin: Origin
    view: Optional[View] = None
    taken_on: Optional[date] = None
    clinical_visit_id: Optional[int] = None
    tooth: Optional[int] = None

    @field_validator("tooth")
    def _valid_tooth(cls, value):
        if value is not None and not is_valid_tooth(value):
            raise ValueError("Pieza dental inválida: usa la numeración FDI (11–48 o 51–85).")
        return value


class ImageVoid(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class PatientImageRevisionResponse(BaseModel):
    revision: int
    origin: Optional[str] = None
    view: Optional[str] = None
    taken_on: Optional[date] = None
    clinical_visit_id: Optional[int] = None
    tooth: Optional[int] = None
    edited_by: PersonRef
    edited_at: DateTime


class ImageAccessResponse(BaseModel):
    user: PersonRef
    accessed_at: DateTime


class PatientImageResponse(BaseModel):
    id: int
    patient_id: int
    clinical_visit: Optional[VisitRef] = None
    tooth: Optional[int] = None
    # null en imágenes anteriores a ODON-178 («sin registrar»).
    origin: Optional[str] = None
    view: Optional[str] = None
    taken_on: Optional[date] = None
    revision: int
    content_type: str
    size_bytes: int
    width: int
    height: int
    consent_id: int
    uploaded_by: PersonRef
    uploaded_at: DateTime
    voided_at: Optional[DateTime] = None
    voided_by: Optional[PersonRef] = None
    void_reason: Optional[str] = None
