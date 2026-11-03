"""Reglas de la agenda: cruces de horario y citas pendientes (ODON-134)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.appointment import (
    BLOCKING_STATUSES,
    Appointment,
    AppointmentStatus,
    AppointmentStatusChange,
)
from app.models.availability import WEEKDAY_LABELS, DoctorAvailabilityBlock
from app.models.clinic import Clinic
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


# --- Estados (ODON-146) --------------------------------------------------------------

S = AppointmentStatus
# Transiciones permitidas. Las terminales solo se corrigen entre sí
# (Atendida ↔ No asistió) y una cancelada solo vuelve a Programada.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    S.SCHEDULED.value: frozenset({S.CONFIRMED.value, S.CANCELLED.value, S.COMPLETED.value, S.NO_SHOW.value}),
    S.CONFIRMED.value: frozenset({S.SCHEDULED.value, S.CANCELLED.value, S.COMPLETED.value, S.NO_SHOW.value}),
    S.CANCELLED.value: frozenset({S.SCHEDULED.value}),
    S.COMPLETED.value: frozenset({S.NO_SHOW.value}),
    S.NO_SHOW.value: frozenset({S.COMPLETED.value}),
}

# Solo tienen sentido cuando la cita ya empezó.
_AFTER_START = frozenset({S.COMPLETED.value, S.NO_SHOW.value})

STATUS_LABELS = {
    S.SCHEDULED.value: "Programada",
    S.CONFIRMED.value: "Confirmada",
    S.COMPLETED.value: "Atendida",
    S.CANCELLED.value: "Cancelada",
    S.NO_SHOW.value: "No asistió",
}


def ensure_transition_allowed(appointment: Appointment, new_status: str) -> None:
    """422/409 si el cambio de estado no tiene sentido para esta cita."""
    current = appointment.status
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Una cita {STATUS_LABELS[current].lower()} no puede pasar a "
            f"{STATUS_LABELS[new_status].lower()}.",
        )

    now = now_utc()
    if new_status in _AFTER_START and appointment.starts_at > now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cita todavía no empieza: no se puede marcar como atendida o no asistió.",
        )
    # Confirmar, quitar la confirmación o cancelar: solo antes de que termine.
    # Reactivar una cancelada exige además un inicio futuro (se valida aparte).
    if new_status not in _AFTER_START and current != S.CANCELLED.value and appointment.ends_at <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cita ya terminó: márcala como atendida o como no asistió.",
        )


def status_change(
    appointment: Appointment,
    from_status: str | None,
    to_status: str,
    user_id: int,
    note: str | None = None,
) -> AppointmentStatusChange:
    """Registro de historial; se agrega con appointment.status_changes.append
    para guardarse en el mismo commit que la cita."""
    return AppointmentStatusChange(
        clinic_id=appointment.clinic_id,
        from_status=from_status,
        to_status=to_status,
        note=note,
        changed_by_user_id=user_id,
    )


# --- Horario del doctor (ODON-142) ---------------------------------------------------

def _format_blocks(blocks) -> str:
    ranges = [f"{b.start_time:%H:%M}–{b.end_time:%H:%M}" for b in blocks]
    return ranges[0] if len(ranges) == 1 else ", ".join(ranges[:-1]) + " y " + ranges[-1]


def ensure_within_schedule(
    db: Session,
    *,
    doctor: Doctor,
    starts_at: datetime,
    duration_minutes: int,
    allow_outside: bool,
) -> None:
    """409 «fuera de horario» si la cita no cabe en un bloque del doctor.

    Decisión del 2026-11-02: se avisa y se permite. Si el usuario confirma,
    el frontend reenvía con allow_outside_schedule=true. Un doctor sin horario
    registrado se agenda libremente."""
    if allow_outside:
        return

    blocks = (
        db.query(DoctorAvailabilityBlock)
        .filter(DoctorAvailabilityBlock.doctor_id == doctor.id)
        .order_by(DoctorAvailabilityBlock.weekday, DoctorAvailabilityBlock.start_time)
        .all()
    )
    if not blocks:
        return

    clinic_tz = ZoneInfo(db.query(Clinic.timezone).filter(Clinic.id == doctor.clinic_id).scalar())
    local_start = starts_at.astimezone(clinic_tz)
    local_end = (starts_at + timedelta(minutes=duration_minutes)).astimezone(clinic_tz)
    weekday = local_start.weekday()
    day_blocks = [b for b in blocks if b.weekday == weekday]

    fits = local_end.date() == local_start.date() and any(
        b.start_time <= local_start.time() and local_end.time() <= b.end_time for b in day_blocks
    )
    if fits:
        return

    day = WEEKDAY_LABELS[weekday]
    # «los sábados», «los domingos»; «los lunes» … «los viernes» no cambian.
    plural = day + "s" if day in ("sábado", "domingo") else day
    schedule = (
        f"Su horario del {day} es {_format_blocks(day_blocks)}."
        if day_blocks
        else f"No atiende los {plural}."
    )
    raise OutsideSchedule(f"{doctor.user.name} no atiende en ese horario. {schedule}")


class OutsideSchedule(HTTPException):
    """409 que el frontend reconoce por outside_schedule=true para pedir confirmación."""

    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
        self.extra = {"outside_schedule": True}
