"""Plan de tratamiento y seguimiento (ODON-158)."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.clinical_visit import ClinicalVisit
from app.models.patient import Patient
from app.models.treatment import (
    TREATMENT_TRANSITIONS,
    Treatment,
    TreatmentStatus,
    TreatmentStatusChange,
)
from app.models.user import User
from app.schemas.treatment_schema import TreatmentCreate, TreatmentStatusUpdate, TreatmentUpdate

audit_logger = logging.getLogger("odontonet.audit")

STATUS_LABELS = {
    TreatmentStatus.PROPOSED: "Propuesto",
    TreatmentStatus.ACCEPTED: "Aceptado",
    TreatmentStatus.IN_PROGRESS: "En curso",
    TreatmentStatus.COMPLETED: "Completado",
    TreatmentStatus.CANCELLED: "Cancelado",
}

# Orden de la lista: lo pendiente primero, después lo cerrado.
_STATUS_ORDER = [
    TreatmentStatus.IN_PROGRESS,
    TreatmentStatus.ACCEPTED,
    TreatmentStatus.PROPOSED,
    TreatmentStatus.COMPLETED,
    TreatmentStatus.CANCELLED,
]


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def _ensure_editable_patient(patient: Patient) -> None:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para registrar o modificar tratamientos.",
        )


def _treatments(db: Session):
    return db.query(Treatment).options(
        joinedload(Treatment.proposed_visit),
        joinedload(Treatment.completed_visit),
        joinedload(Treatment.created_by),
        joinedload(Treatment.updated_by),
    )


def _last_change(db: Session, treatment_id: int) -> TreatmentStatusChange:
    return (
        db.query(TreatmentStatusChange)
        .filter(TreatmentStatusChange.treatment_id == treatment_id)
        .order_by(TreatmentStatusChange.id.desc())
        .first()
    )


def _visit_ref(visit: Optional[ClinicalVisit]) -> Optional[dict]:
    if visit is None:
        return None
    return {"id": visit.id, "visit_at": visit.visit_at, "reason": visit.reason, "voided": visit.voided_at is not None}


def _person(user: User) -> dict:
    return {"id": user.id, "name": user.name}


def to_response(db: Session, treatment: Treatment) -> dict:
    last = _last_change(db, treatment.id)
    return {
        "id": treatment.id,
        "patient_id": treatment.patient_id,
        "procedure": treatment.procedure,
        "tooth": treatment.tooth,
        "notes": treatment.notes,
        "planned_date": treatment.planned_date,
        "status": treatment.status,
        "status_reason": last.reason,
        "status_changed_at": last.changed_at,
        "proposed_visit": _visit_ref(treatment.proposed_visit),
        "completed_visit": _visit_ref(treatment.completed_visit),
        "created_by": _person(treatment.created_by),
        "created_at": treatment.created_at,
        "updated_by": _person(treatment.updated_by),
        "updated_at": treatment.updated_at,
    }


def list_treatments(db: Session, patient_id: int) -> list[Treatment]:
    treatments = _treatments(db).filter(Treatment.patient_id == patient_id).all()
    order = {s.value: i for i, s in enumerate(_STATUS_ORDER)}
    return sorted(treatments, key=lambda t: (order[t.status], -t.id))


def get_treatment(db: Session, patient_id: int, treatment_id: int) -> Treatment:
    treatment = (
        _treatments(db).filter(Treatment.id == treatment_id, Treatment.patient_id == patient_id).first()
    )
    if treatment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tratamiento no encontrado.")
    return treatment


def list_status_changes(db: Session, treatment: Treatment) -> list[dict]:
    changes = (
        db.query(TreatmentStatusChange)
        .options(joinedload(TreatmentStatusChange.changed_by))
        .filter(TreatmentStatusChange.treatment_id == treatment.id)
        .order_by(TreatmentStatusChange.id.desc())
        .all()
    )
    return [
        {
            "from_status": change.from_status,
            "to_status": change.to_status,
            "reason": change.reason,
            "changed_by": _person(change.changed_by),
            "changed_at": change.changed_at,
        }
        for change in changes
    ]


def _patient_visit(db: Session, patient: Patient, visit_id: int, purpose: str) -> ClinicalVisit:
    """Consulta del mismo paciente y no anulada; si no, 422 sin revelar nada."""
    visit = (
        db.query(ClinicalVisit)
        .filter(ClinicalVisit.id == visit_id, ClinicalVisit.patient_id == patient.id)
        .first()
    )
    if visit is None:
        raise _unprocessable(f"La consulta {purpose} no pertenece a este paciente.")
    if visit.voided_at is not None:
        raise _unprocessable(f"La consulta {purpose} está anulada.")
    return visit


def _record_change(db, treatment, from_status, to_status, user, reason=None) -> None:
    db.add(
        TreatmentStatusChange(
            clinic_id=treatment.clinic_id,
            treatment_id=treatment.id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            changed_by_user_id=user.id,
        )
    )


def create_treatment(db: Session, patient: Patient, data: TreatmentCreate, user: User) -> Treatment:
    _ensure_editable_patient(patient)
    if data.proposed_visit_id is not None:
        _patient_visit(db, patient, data.proposed_visit_id, "de la propuesta")

    treatment = Treatment(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        procedure=data.procedure,
        tooth=data.tooth,
        notes=data.notes,
        planned_date=data.planned_date,
        proposed_visit_id=data.proposed_visit_id,
        status=TreatmentStatus.PROPOSED.value,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(treatment)
    db.flush()
    _record_change(db, treatment, None, TreatmentStatus.PROPOSED.value, user)
    db.commit()

    audit_logger.info(
        "treatment.created treatment_id=%s patient_id=%s user_id=%s clinic_id=%s",
        treatment.id, patient.id, user.id, patient.clinic_id,
    )
    return get_treatment(db, patient.id, treatment.id)


def _lock(db: Session, treatment: Treatment) -> None:
    """Bloquea la fila del tratamiento (solo esa tabla) y relee su estado: un
    cambio simultáneo espera y ve el estado ya actualizado."""
    db.execute(select(Treatment.id).where(Treatment.id == treatment.id).with_for_update())
    db.refresh(treatment)


def _ensure_open(treatment: Treatment) -> None:
    if treatment.status in (TreatmentStatus.COMPLETED.value, TreatmentStatus.CANCELLED.value):
        label = STATUS_LABELS[TreatmentStatus(treatment.status)].lower()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El tratamiento está {label} y ya no se puede modificar.",
        )


def update_treatment(
    db: Session, patient: Patient, treatment: Treatment, data: TreatmentUpdate, user: User
) -> Treatment:
    _ensure_editable_patient(patient)
    _lock(db, treatment)
    _ensure_open(treatment)

    changes = data.dict(exclude_unset=True)
    if "procedure" in changes and changes["procedure"] is None:
        raise _unprocessable("Indica el procedimiento.")
    if changes.get("proposed_visit_id") is not None and changes["proposed_visit_id"] != treatment.proposed_visit_id:
        _patient_visit(db, patient, changes["proposed_visit_id"], "de la propuesta")

    changed = sorted(field for field, value in changes.items() if getattr(treatment, field) != value)
    if not changed:
        return treatment

    for field in changed:
        setattr(treatment, field, changes[field])
    treatment.updated_by_user_id = user.id
    treatment.updated_at = datetime.now(timezone.utc)
    db.commit()

    audit_logger.info(
        "treatment.updated treatment_id=%s user_id=%s clinic_id=%s fields=%s",
        treatment.id, user.id, patient.clinic_id, ",".join(changed),
    )
    db.expire_all()
    return get_treatment(db, patient.id, treatment.id)


def change_status(
    db: Session, patient: Patient, treatment: Treatment, data: TreatmentStatusUpdate, user: User
) -> Treatment:
    _ensure_editable_patient(patient)
    _lock(db, treatment)

    current = TreatmentStatus(treatment.status)
    target = data.status
    if target not in TREATMENT_TRANSITIONS[current]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede pasar de «{STATUS_LABELS[current]}» a «{STATUS_LABELS[target]}».",
        )

    if target == TreatmentStatus.CANCELLED and not data.reason:
        raise _unprocessable("Indica el motivo de la cancelación.")
    if target == TreatmentStatus.COMPLETED:
        if data.completed_visit_id is None:
            raise _unprocessable("Indica la consulta en que se realizó el tratamiento.")
        _patient_visit(db, patient, data.completed_visit_id, "de realización")
        treatment.completed_visit_id = data.completed_visit_id

    treatment.status = target.value
    treatment.updated_by_user_id = user.id
    treatment.updated_at = datetime.now(timezone.utc)
    _record_change(db, treatment, current.value, target.value, user, data.reason)
    db.commit()

    audit_logger.info(
        "treatment.status_changed treatment_id=%s from=%s to=%s user_id=%s clinic_id=%s",
        treatment.id, current.value, target.value, user.id, patient.clinic_id,
    )
    db.expire_all()
    return get_treatment(db, patient.id, treatment.id)
