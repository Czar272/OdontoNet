"""Periodontograma manual del paciente (ODON-9).

Administración y doctores leen y registran exámenes; solo quien registró un
examen o administración lo edita, finaliza o anula. Recepción no accede
(docs/PERMISSIONS.md). La clínica sale siempre del token.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.periodontal_schema import (
    ExamCreate,
    ExamFinalize,
    ExamListItem,
    ExamResponse,
    ExamRevisionResponse,
    ExamUpdate,
    ExamVoid,
)
from app.services import periodontal_service as service

CLINICAL_ROLES = (Role.ADMIN, Role.DOCTOR)
clinical_user = require_roles(*CLINICAL_ROLES)

router = APIRouter(
    prefix="/patients/{patient_id}/periodontal-exams",
    tags=["Periodontal exams"],
    dependencies=[Depends(clinical_user)],
)


@router.get("", response_model=list[ExamListItem])
def list_exams(patient_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Exámenes del paciente, del más reciente al más antiguo (anulados incluidos), con su resumen."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return [service.to_list_item(exam) for exam in service.list_exams(db, patient_id)]


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(patient_id: int, data: ExamCreate, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Registra un examen en borrador con las 32 piezas permanentes y 6 sitios por pieza."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(service.create_exam(db, patient, data, user))


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(patient_id: int, exam_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(service.get_exam(db, patient_id, exam_id))


@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(
    patient_id: int, exam_id: int, data: ExamUpdate, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Guarda el borrador completo con base_revision (solo autor o administración)."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    exam = service.get_exam(db, patient_id, exam_id)
    return service.to_response(service.update_exam(db, patient, exam, data, user))


@router.post("/{exam_id}/finalize", response_model=ExamResponse)
def finalize_exam(
    patient_id: int, exam_id: int, data: ExamFinalize, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Finaliza el borrador: desde entonces es inmutable."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    exam = service.get_exam(db, patient_id, exam_id)
    return service.to_response(service.finalize_exam(db, patient, exam, data.base_revision, user))


@router.post("/{exam_id}/void", response_model=ExamResponse)
def void_exam(
    patient_id: int, exam_id: int, data: ExamVoid, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Anula el examen con un motivo. No se borra: sigue visible como anulado."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    exam = service.get_exam(db, patient_id, exam_id)
    return service.to_response(service.void_exam(db, patient, exam, data.reason, user))


@router.get("/{exam_id}/revisions", response_model=list[ExamRevisionResponse])
def list_revisions(patient_id: int, exam_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Guardados del examen, del más reciente al primero."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.list_revisions(db, service.get_exam(db, patient_id, exam_id))
