"""Consentimiento del paciente para fotografías clínicas (ODON-170).

Versionado como la historia médica: cada registro es una versión nueva y
ninguna se modifica ni se borra. Sin una versión vigente con granted = true
no se pueden subir imágenes del paciente.
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.photo_consent import PatientPhotoConsent
from app.models.user import User
from app.schemas.patient_image_schema import PhotoConsentCreate
from app.services import audit_service


def to_response(consent: PatientPhotoConsent) -> dict:
    return {
        "id": consent.id,
        "version": consent.version,
        "granted": consent.granted,
        "research_use": consent.research_use,
        "signed_on": consent.signed_on,
        "notes": consent.notes,
        "recorded_by": {"id": consent.recorded_by.id, "name": consent.recorded_by.name},
        "recorded_at": consent.recorded_at,
    }


def list_consents(db: Session, patient_id: int) -> list[PatientPhotoConsent]:
    return (
        db.query(PatientPhotoConsent)
        .options(joinedload(PatientPhotoConsent.recorded_by))
        .filter(PatientPhotoConsent.patient_id == patient_id)
        .order_by(PatientPhotoConsent.version.desc())
        .all()
    )


def current_consent(db: Session, patient_id: int) -> Optional[PatientPhotoConsent]:
    return (
        db.query(PatientPhotoConsent)
        .filter(PatientPhotoConsent.patient_id == patient_id)
        .order_by(PatientPhotoConsent.version.desc())
        .first()
    )


def require_active_consent(db: Session, patient: Patient) -> PatientPhotoConsent:
    consent = current_consent(db, patient.id)
    if consent is None or not consent.granted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El paciente no tiene un consentimiento vigente para fotografías clínicas. "
                "Regístralo antes de subir imágenes."
            ),
        )
    return consent


def record_consent(db: Session, patient: Patient, data: PhotoConsentCreate, user: User) -> PatientPhotoConsent:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para registrar el consentimiento.",
        )
    clinic = db.get(Clinic, patient.clinic_id)
    today = datetime.now(timezone.utc).astimezone(ZoneInfo(clinic.timezone)).date()
    if data.signed_on > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La fecha del documento no puede ser futura.",
        )

    last = (
        db.query(func.max(PatientPhotoConsent.version))
        .filter(PatientPhotoConsent.patient_id == patient.id)
        .scalar()
    )
    consent = PatientPhotoConsent(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        version=(last or 0) + 1,
        granted=data.granted,
        research_use=data.research_use,
        signed_on=data.signed_on,
        notes=data.notes,
        recorded_by_user_id=user.id,
    )
    db.add(consent)
    try:
        db.flush()
        audit_service.record(
            db, user, "photo_consent.recorded", "photo_consent", consent.id,
            patient_id=patient.id, clinic_id=patient.clinic_id,
            detail=f"granted={consent.granted} research_use={consent.research_use}",
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Otra persona registró el consentimiento al mismo tiempo. Recarga y revísalo.",
        )
    db.refresh(consent)

    return consent
