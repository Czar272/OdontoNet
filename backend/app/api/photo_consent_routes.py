"""Consentimiento del paciente para fotografías clínicas (ODON-170).

Administración y doctores lo consultan y registran; Recepción no accede
(docs/PERMISSIONS.md). Cada registro es una versión nueva; revocar es
registrar granted = false.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.patient_image_schema import PhotoConsentCreate, PhotoConsentResponse, PhotoConsentStatus
from app.services import photo_consent_service as service
from app.services.patient_image_service import get_clinic_patient

clinical_user = require_roles(Role.ADMIN, Role.DOCTOR)

router = APIRouter(
    prefix="/patients/{patient_id}/photo-consent",
    tags=["Images"],
    dependencies=[Depends(clinical_user)],
)


@router.get("", response_model=PhotoConsentStatus)
def get_photo_consent(patient_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Versión vigente (null si nunca se registró) e historial completo."""
    get_clinic_patient(db, patient_id, user.clinic_id)
    history = [service.to_response(c) for c in service.list_consents(db, patient_id)]
    return {"current": history[0] if history else None, "history": history}


@router.post("", response_model=PhotoConsentResponse, status_code=status.HTTP_201_CREATED)
def record_photo_consent(
    patient_id: int, data: PhotoConsentCreate, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Registra una versión nueva (otorgar, actualizar o revocar)."""
    patient = get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(service.record_consent(db, patient, data, user))
