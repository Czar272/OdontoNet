"""Historia médica y odontológica versionada (ODON-150)."""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.medical_history import PatientMedicalHistory
from app.models.patient import Patient
from app.models.user import User
from app.schemas.medical_history_schema import MedicalHistoryCreate

audit_logger = logging.getLogger("odontonet.audit")


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def _versions(db: Session, patient_id: int):
    return (
        db.query(PatientMedicalHistory)
        .options(joinedload(PatientMedicalHistory.created_by))
        .filter(PatientMedicalHistory.patient_id == patient_id)
    )


def current_history(db: Session, patient_id: int) -> Optional[PatientMedicalHistory]:
    return _versions(db, patient_id).order_by(PatientMedicalHistory.version.desc()).first()


def list_versions(db: Session, patient_id: int) -> list[PatientMedicalHistory]:
    return _versions(db, patient_id).order_by(PatientMedicalHistory.version.desc()).all()


def get_version(db: Session, patient_id: int, version: int) -> PatientMedicalHistory:
    history = _versions(db, patient_id).filter(PatientMedicalHistory.version == version).first()
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Versión no encontrada.")
    return history


def _stale(current_version: Optional[int]) -> HTTPException:
    exc = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "La historia médica cambió mientras la editabas. "
            "Revisa la versión actual antes de guardar."
        ),
    )
    exc.extra = {"current_version": current_version}
    return exc


def create_version(
    db: Session, patient: Patient, data: MedicalHistoryCreate, author: User
) -> PatientMedicalHistory:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para actualizar su historia médica.",
        )

    current = current_history(db, patient.id)
    current_version = current.version if current else None
    if data.base_version != current_version:
        raise _stale(current_version)

    content = data.dict(exclude={"base_version"})
    history = PatientMedicalHistory(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        version=(current_version or 0) + 1,
        created_by_user_id=author.id,
        **content,
    )
    db.add(history)
    try:
        db.commit()
    except IntegrityError:
        # Dos guardados simultáneos sobre la misma versión: gana el primero.
        db.rollback()
        latest = current_history(db, patient.id)
        raise _stale(latest.version if latest else None)

    audit_logger.info(
        "medical_history.created patient_id=%s version=%s user_id=%s clinic_id=%s",
        patient.id, history.version, author.id, patient.clinic_id,
    )
    return get_version(db, patient.id, history.version)
