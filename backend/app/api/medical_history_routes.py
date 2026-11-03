"""Historia médica y odontológica del paciente (ODON-150).

Lectura: administración, doctores y recepción. Escritura: administración y
doctores (docs/PERMISSIONS.md). La clínica sale siempre del token.
"""
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_clinic_id
from app.auth.permissions import ALL_ROLES, Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.medical_history_schema import (
    MedicalHistoryCreate,
    MedicalHistoryResponse,
    MedicalHistoryVersionSummary,
)
from app.services import medical_history_service as service

router = APIRouter(
    prefix="/patients/{patient_id}/medical-history",
    tags=["Medical history"],
    dependencies=[Depends(require_roles(*ALL_ROLES))],
)


@router.get("", response_model=Optional[MedicalHistoryResponse])
def get_current_history(
    patient_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Versión vigente, o null si el paciente aún no tiene historia."""
    service.get_clinic_patient(db, patient_id, clinic_id)
    return service.current_history(db, patient_id)


@router.get("/versions", response_model=list[MedicalHistoryVersionSummary])
def list_history_versions(
    patient_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Versiones de la más reciente a la más antigua, con autor y fecha."""
    service.get_clinic_patient(db, patient_id, clinic_id)
    return service.list_versions(db, patient_id)


@router.get("/versions/{version}", response_model=MedicalHistoryResponse)
def get_history_version(
    patient_id: int,
    version: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    service.get_clinic_patient(db, patient_id, clinic_id)
    return service.get_version(db, patient_id, version)


@router.post("", response_model=MedicalHistoryResponse, status_code=status.HTTP_201_CREATED)
def save_history(
    patient_id: int,
    data: MedicalHistoryCreate,
    db: Session = Depends(get_db),
    author: User = Depends(require_roles(Role.ADMIN, Role.DOCTOR)),
):
    """Guarda la historia completa como una versión nueva. No modifica las anteriores."""
    patient = service.get_clinic_patient(db, patient_id, author.clinic_id)
    return service.create_version(db, patient, data, author)
