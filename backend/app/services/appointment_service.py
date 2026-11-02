"""Reglas de la agenda: cruces de horario y citas pendientes (ODON-134)."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus, BLOCKING_STATUSES

# Citas que todavía se pueden reprogramar y que cuentan como pendientes.
PENDING_STATUSES = (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)

DOCTOR_OVERLAP_DETAIL = "El doctor ya tiene una cita que se cruza con ese horario."
PATIENT_OVERLAP_DETAIL = "El paciente ya tiene una cita que se cruza con ese horario."

_CONSTRAINT_DETAILS = {
    "ex_appointments_doctor_overlap": DOCTOR_OVERLAP_DETAIL,
    "ex_appointments_patient_overlap": PATIENT_OVERLAP_DETAIL,
}


def _ends_at_sql():
    return func.appointment_end(Appointment.starts_at, Appointment.duration_minutes)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def count_upcoming_appointments(db: Session, patient_id: int) -> int:
    """Citas pendientes que aún no terminan (bloquean el archivo del paciente)."""
    return (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.status.in_(PENDING_STATUSES),
            _ends_at_sql() > now_utc(),
        )
        .scalar()
    )


def ensure_not_in_past(starts_at: datetime) -> None:
    # Se compara con el inicio del minuto actual: agendar "ahora" es válido.
    current_minute = now_utc().replace(second=0, microsecond=0)
    if starts_at < current_minute:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La cita no puede empezar en el pasado.",
        )


def ensure_no_overlap(
    db: Session,
    *,
    doctor_id: int,
    patient_id: int,
    starts_at: datetime,
    duration_minutes: int,
    exclude_id: int | None = None,
) -> None:
    """409 si el doctor o el paciente ya tienen una cita activa que se cruce.

    Es la validación con mensaje claro; las restricciones de exclusión de la
    base son la garantía final cuando dos peticiones llegan a la vez."""
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    overlapping = db.query(Appointment.doctor_id, Appointment.patient_id).filter(
        Appointment.status.in_(BLOCKING_STATUSES),
        Appointment.starts_at < literal(ends_at),
        _ends_at_sql() > literal(starts_at),
        (Appointment.doctor_id == doctor_id) | (Appointment.patient_id == patient_id),
    )
    if exclude_id is not None:
        overlapping = overlapping.filter(Appointment.id != exclude_id)

    rows = overlapping.all()
    if any(row.doctor_id == doctor_id for row in rows):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DOCTOR_OVERLAP_DETAIL)
    if rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=PATIENT_OVERLAP_DETAIL)


def commit_appointment(db: Session) -> None:
    """Guarda y traduce un cruce detectado por la base (carrera entre
    peticiones) al mismo 409 que da la validación previa."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig)
        for constraint, detail in _CONSTRAINT_DETAILS.items():
            if constraint in message:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise
