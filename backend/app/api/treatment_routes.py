"""Plan de tratamiento y seguimiento del paciente (ODON-158).

Administración y doctores leen, registran, editan y cambian el estado de
cualquier tratamiento de su clínica; el historial registra quién hizo cada
cambio. Recepción no accede (docs/PERMISSIONS.md).
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.treatment_schema import (
    TreatmentCreate,
    TreatmentResponse,
    TreatmentStatusChangeResponse,
    TreatmentStatusUpdate,
    TreatmentUpdate,
)
from app.services import treatment_service as service

clinical_user = require_roles(Role.ADMIN, Role.DOCTOR)

router = APIRouter(
    prefix="/patients/{patient_id}/treatments",
    tags=["Treatments"],
    dependencies=[Depends(clinical_user)],
)


@router.get("", response_model=list[TreatmentResponse])
def list_treatments(patient_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Pendientes primero (en curso, aceptados, propuestos) y después los cerrados."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return [service.to_response(db, t) for t in service.list_treatments(db, patient_id)]


@router.post("", response_model=TreatmentResponse, status_code=status.HTTP_201_CREATED)
def create_treatment(
    patient_id: int, data: TreatmentCreate, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Registra un tratamiento propuesto."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(db, service.create_treatment(db, patient, data, user))


@router.get("/{treatment_id}", response_model=TreatmentResponse)
def get_treatment(
    patient_id: int, treatment_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(db, service.get_treatment(db, patient_id, treatment_id))


@router.patch("/{treatment_id}", response_model=TreatmentResponse)
def update_treatment(
    patient_id: int,
    treatment_id: int,
    data: TreatmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Edita un tratamiento abierto (no completado ni cancelado)."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    treatment = service.get_treatment(db, patient_id, treatment_id)
    return service.to_response(db, service.update_treatment(db, patient, treatment, data, user))


@router.post("/{treatment_id}/status", response_model=TreatmentResponse)
def change_treatment_status(
    patient_id: int,
    treatment_id: int,
    data: TreatmentStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Cambia el estado. Cancelar exige motivo; completar exige la consulta en que se realizó."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    treatment = service.get_treatment(db, patient_id, treatment_id)
    return service.to_response(db, service.change_status(db, patient, treatment, data, user))


@router.get("/{treatment_id}/history", response_model=list[TreatmentStatusChangeResponse])
def treatment_history(
    patient_id: int, treatment_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Cambios de estado, del más reciente al alta."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.list_status_changes(db, service.get_treatment(db, patient_id, treatment_id))
