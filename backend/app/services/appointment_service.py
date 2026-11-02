"""Reglas de la agenda: cruces de horario y citas pendientes (ODON-134)."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment, AppointmentStatus, BLOCKING_STATUSES
from app.models.doctor import Doctor

# Citas que todavía se pueden reprogramar y que cuentan como pendientes.
PENDING_STATUSES = (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)

DOCTOR_OVERLAP_DETAIL = "El doctor ya tiene una cita que se cruza con ese horario."
PATIENT_OVERLAP_DETAIL = "El paciente ya tiene una cita que se cruza con ese horario."

_CONSTRAINT_DETAILS = {
    "ex_appointments_doctor_overlap": DOCTOR_OVERLAP_DETAIL,
    "ex_appointments_patient_overlap": PATIENT_OVERLAP_DETAIL,
}


class AppointmentConflict(HTTPException):
    """409 por cruce de horario, con la cita que choca en "conflict".

    El mensaje nombra al doctor; las horas van en "conflict" (ISO con zona
    horaria) para que el navegador las muestre en su hora local."""

    def __init__(self, detail: str, appointment: Appointment | None = None):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
        self.extra = {}
        if appointment is not None:
            self.extra["conflict"] = {
                "appointment_id": appointment.id,
                "starts_at": appointment.starts_at.isoformat(),
                "ends_at": appointment.ends_at.isoformat(),
                "doctor_id": appointment.doctor_id,
                "doctor_name": appointment.doctor.user.name,
                "patient_id": appointment.patient_id,
                "patient_name": f"{appointment.patient.first_name} {appointment.patient.last_name}",
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
    overlapping = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor).joinedload(Doctor.user),
        )
        .filter(
            Appointment.status.in_(BLOCKING_STATUSES),
            Appointment.starts_at < literal(ends_at),
            _ends_at_sql() > literal(starts_at),
            (Appointment.doctor_id == doctor_id) | (Appointment.patient_id == patient_id),
        )
        .order_by(Appointment.starts_at)
    )
    if exclude_id is not None:
        overlapping = overlapping.filter(Appointment.id != exclude_id)

    rows = overlapping.all()
    # Primero el cruce del doctor (es el que se resuelve cambiando el horario).
    by_doctor = next((row for row in rows if row.doctor_id == doctor_id), None)
    if by_doctor is not None:
        raise AppointmentConflict(
            f"{by_doctor.doctor.user.name} ya tiene una cita que se cruza con ese horario.",
            by_doctor,
        )
    if rows:
        raise AppointmentConflict(
            f"El paciente ya tiene una cita con {rows[0].doctor.user.name} "
            "que se cruza con ese horario.",
            rows[0],
        )


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
                # La otra cita llegó en paralelo: no hay detalle fiable que mostrar.
                raise AppointmentConflict(detail) from exc
        raise
