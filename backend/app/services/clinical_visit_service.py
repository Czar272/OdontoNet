"""Consultas clínicas con revisiones y anulación (ODON-154)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.permissions import Role
from app.models.clinic import Clinic
from app.models.clinical_visit import VISIT_CONTENT_FIELDS, ClinicalVisit, ClinicalVisitRevision
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.clinical_visit_schema import VisitContent, VisitUpdate
from app.services import audit_service
from app.services.doctor_service import ensure_assignable_doctor


# Margen para relojes desajustados: una consulta no puede registrarse a futuro.
FUTURE_TOLERANCE = timedelta(minutes=5)


def _person(user: User) -> dict:
    return {"id": user.id, "name": user.name}


def _doctor_ref(doctor: Doctor) -> dict:
    # id del perfil de doctor (el que se envía como doctor_id), nombre del usuario.
    return {"id": doctor.id, "name": doctor.user.name}


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def _visits(db: Session):
    return db.query(ClinicalVisit).options(
        joinedload(ClinicalVisit.doctor).joinedload(Doctor.user),
        joinedload(ClinicalVisit.created_by),
        joinedload(ClinicalVisit.voided_by),
    )


def list_visits(db: Session, patient_id: int) -> list[ClinicalVisit]:
    return (
        _visits(db)
        .filter(ClinicalVisit.patient_id == patient_id)
        .order_by(ClinicalVisit.visit_at.desc(), ClinicalVisit.id.desc())
        .all()
    )


def get_visit(db: Session, patient_id: int, visit_id: int) -> ClinicalVisit:
    visit = (
        _visits(db)
        .filter(ClinicalVisit.id == visit_id, ClinicalVisit.patient_id == patient_id)
        .first()
    )
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada.")
    return visit


def _last_revision(db: Session, visit_id: int) -> ClinicalVisitRevision:
    return (
        db.query(ClinicalVisitRevision)
        .options(joinedload(ClinicalVisitRevision.edited_by))
        .filter(ClinicalVisitRevision.visit_id == visit_id)
        .order_by(ClinicalVisitRevision.revision.desc())
        .first()
    )


def to_response(db: Session, visit: ClinicalVisit) -> dict:
    last = _last_revision(db, visit.id)
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "revision": visit.revision,
        **{field: getattr(visit, field) for field in VISIT_CONTENT_FIELDS if field != "doctor_id"},
        "doctor": _doctor_ref(visit.doctor),
        "created_by": _person(visit.created_by),
        "created_at": visit.created_at,
        "updated_by": _person(last.edited_by),
        "updated_at": last.edited_at,
        "voided_at": visit.voided_at,
        "voided_by": _person(visit.voided_by) if visit.voided_by else None,
        "void_reason": visit.void_reason,
    }


def list_revisions(db: Session, visit: ClinicalVisit) -> list[dict]:
    revisions = (
        db.query(ClinicalVisitRevision)
        .options(
            joinedload(ClinicalVisitRevision.edited_by),
            joinedload(ClinicalVisitRevision.doctor).joinedload(Doctor.user),
        )
        .filter(ClinicalVisitRevision.visit_id == visit.id)
        .order_by(ClinicalVisitRevision.revision.desc())
        .all()
    )
    return [
        {
            "revision": rev.revision,
            "edited_by": _person(rev.edited_by),
            "edited_at": rev.edited_at,
            **{field: getattr(rev, field) for field in VISIT_CONTENT_FIELDS if field != "doctor_id"},
            "doctor": _doctor_ref(rev.doctor),
        }
        for rev in revisions
    ]


def _ensure_editable_patient(patient: Patient) -> None:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para registrar o modificar consultas.",
        )


def _validate_content(db: Session, patient: Patient, data: VisitContent, current_doctor_id=None) -> None:
    if data.visit_at > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La fecha de atención no puede estar en el futuro.",
        )

    # Un doctor ya registrado en la consulta se conserva aunque hoy esté inactivo.
    if data.doctor_id != current_doctor_id:
        ensure_assignable_doctor(db, data.doctor_id, patient.clinic_id)

    if data.next_visit_date is not None:
        clinic = db.get(Clinic, patient.clinic_id)
        visit_day = data.visit_at.astimezone(ZoneInfo(clinic.timezone)).date()
        if data.next_visit_date <= visit_day:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="La próxima cita sugerida debe ser posterior a la consulta.",
            )


def _content(data: VisitContent) -> dict:
    return {field: getattr(data, field) for field in VISIT_CONTENT_FIELDS}


def _add_revision(db: Session, visit: ClinicalVisit, editor: User) -> None:
    db.add(
        ClinicalVisitRevision(
            clinic_id=visit.clinic_id,
            visit_id=visit.id,
            revision=visit.revision,
            edited_by_user_id=editor.id,
            **{field: getattr(visit, field) for field in VISIT_CONTENT_FIELDS},
        )
    )


def create_visit(db: Session, patient: Patient, data: VisitContent, author: User) -> ClinicalVisit:
    _ensure_editable_patient(patient)
    _validate_content(db, patient, data)

    visit = ClinicalVisit(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        revision=1,
        created_by_user_id=author.id,
        **_content(data),
    )
    db.add(visit)
    db.flush()
    _add_revision(db, visit, author)
    audit_service.record(
        db, author, "clinical_visit.created", "clinical_visit", visit.id,
        patient_id=patient.id, clinic_id=patient.clinic_id,
    )
    db.commit()

    return get_visit(db, patient.id, visit.id)


def _ensure_can_modify(visit: ClinicalVisit, user: User) -> None:
    if user.role != Role.ADMIN.value and visit.created_by_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo quien registró la consulta o administración pueden modificarla.",
        )
    if visit.voided_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="La consulta está anulada y no se puede modificar."
        )


def update_visit(
    db: Session, patient: Patient, visit: ClinicalVisit, data: VisitUpdate, editor: User
) -> ClinicalVisit:
    _ensure_can_modify(visit, editor)
    _ensure_editable_patient(patient)

    if data.base_revision != visit.revision:
        exc = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La consulta cambió mientras la editabas. Revisa la versión actual antes de guardar.",
        )
        exc.extra = {"current_revision": visit.revision}
        raise exc

    _validate_content(db, patient, data, current_doctor_id=visit.doctor_id)

    new_content = _content(data)
    changed = sorted(field for field, value in new_content.items() if getattr(visit, field) != value)
    if not changed:
        return visit

    for field in changed:
        setattr(visit, field, new_content[field])
    visit.revision += 1
    _add_revision(db, visit, editor)
    try:
        db.flush()
        audit_service.record(
            db, editor, "clinical_visit.updated", "clinical_visit", visit.id,
            patient_id=patient.id, fields=changed, clinic_id=patient.clinic_id,
            detail=f"revision={visit.revision} fields={','.join(changed)}",
        )
        db.commit()
    except IntegrityError:
        # Otra edición simultánea ya creó esta revisión.
        db.rollback()
        exc = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La consulta cambió mientras la editabas. Revisa la versión actual antes de guardar.",
        )
        exc.extra = {"current_revision": get_visit(db, patient.id, visit.id).revision}
        raise exc

    return get_visit(db, patient.id, visit.id)


def void_visit(db: Session, patient: Patient, visit: ClinicalVisit, reason: str, user: User) -> ClinicalVisit:
    _ensure_can_modify(visit, user)
    _ensure_editable_patient(patient)

    visit.voided_at = datetime.now(timezone.utc)
    visit.voided_by_user_id = user.id
    visit.void_reason = reason
    # El motivo no se guarda en la auditoría: solo el nombre del campo.
    audit_service.record(
        db, user, "clinical_visit.voided", "clinical_visit", visit.id,
        patient_id=patient.id, fields=["void_reason", "voided_at"], clinic_id=patient.clinic_id,
    )
    db.commit()

    return get_visit(db, patient.id, visit.id)
