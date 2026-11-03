"""Consultas clínicas del paciente (ODON-154).

Administración y doctores las leen y registran; solo quien registró una
consulta o administración la edita o anula. Recepción no accede
(docs/PERMISSIONS.md). La clínica sale siempre del token.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.clinical_visit_schema import (
    VisitCreate,
    VisitResponse,
    VisitRevisionResponse,
    VisitUpdate,
    VisitVoid,
)
from app.services import clinical_visit_service as service

CLINICAL_ROLES = (Role.ADMIN, Role.DOCTOR)

router = APIRouter(
    prefix="/patients/{patient_id}/visits",
    tags=["Clinical visits"],
    dependencies=[Depends(require_roles(*CLINICAL_ROLES))],
)

clinical_user = require_roles(*CLINICAL_ROLES)


@router.get("", response_model=list[VisitResponse])
def list_visits(patient_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Consultas del paciente, de la más reciente a la más antigua (anuladas incluidas)."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return [service.to_response(db, visit) for visit in service.list_visits(db, patient_id)]


@router.post("", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
def create_visit(
    patient_id: int, data: VisitCreate, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(db, service.create_visit(db, patient, data, user))


@router.get("/{visit_id}", response_model=VisitResponse)
def get_visit(patient_id: int, visit_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(db, service.get_visit(db, patient_id, visit_id))


@router.put("/{visit_id}", response_model=VisitResponse)
def update_visit(
    patient_id: int,
    visit_id: int,
    data: VisitUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Reemplaza el contenido y guarda una revisión nueva (solo autor o administración)."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    visit = service.get_visit(db, patient_id, visit_id)
    return service.to_response(db, service.update_visit(db, patient, visit, data, user))


@router.post("/{visit_id}/void", response_model=VisitResponse)
def void_visit(
    patient_id: int,
    visit_id: int,
    data: VisitVoid,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Anula la consulta con un motivo. No se borra: sigue visible como anulada."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    visit = service.get_visit(db, patient_id, visit_id)
    return service.to_response(db, service.void_visit(db, patient, visit, data.reason, user))


@router.get("/{visit_id}/revisions", response_model=list[VisitRevisionResponse])
def list_revisions(
    patient_id: int, visit_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Historial de cambios, de la revisión más reciente a la primera."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.list_revisions(db, service.get_visit(db, patient_id, visit_id))
