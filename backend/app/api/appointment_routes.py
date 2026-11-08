from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam, status
from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload

from app.auth.dependencies import get_current_clinic_id, get_current_user
from app.auth.permissions import ALL_ROLES, require_roles
from app.database.dependencies import get_db
from app.models.appointment import Appointment, AppointmentStatus, AppointmentStatusChange
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment_schema import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusChangeResponse,
    AppointmentStatusUpdate,
    AppointmentUpdate,
)
from app.services.appointment_service import (
    PENDING_STATUSES,
    commit_appointment,
    ensure_no_overlap,
    ensure_not_in_past,
    ensure_transition_allowed,
    ensure_within_schedule,
    status_change,
)
from app.services import audit_service
from app.services.doctor_service import ensure_assignable_doctor

# Administración, doctores y recepción gestionan la agenda (docs/PERMISSIONS.md).
router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
    dependencies=[Depends(require_roles(*ALL_ROLES))],
)

MAX_RANGE_DAYS = 93


def _clinic_appointments(db: Session, clinic_id: int) -> Query:
    """Citas de la clínica con paciente, doctor y usuario del doctor cargados."""
    return (
        db.query(Appointment)
        .options(
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor).joinedload(Doctor.user),
        )
        .filter(Appointment.clinic_id == clinic_id)
    )


def _get_clinic_appointment(db: Session, appointment_id: int, clinic_id: int) -> Appointment:
    appointment = (
        _clinic_appointments(db, clinic_id).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada.")
    return appointment


def _ensure_schedulable_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        .first()
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El paciente seleccionado no pertenece a la clínica.",
        )
    if patient.archived_at is not None:
        # Decisión del 2026-11-02: no se agenda a pacientes archivados.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para agendarle citas.",
        )
    return patient


def _ensure_aware(value: datetime | None, field: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"El parámetro {field} debe incluir la zona horaria.",
        )


@router.get("/", response_model=list[AppointmentResponse])
def list_appointments(
    start: datetime | None = QueryParam(None, description="Inicio del rango (con zona horaria)."),
    end: datetime | None = QueryParam(None, description="Fin del rango (con zona horaria)."),
    doctor_id: int | None = None,
    patient_id: int | None = None,
    status_filter: list[AppointmentStatus] | None = QueryParam(
        None, alias="status", description="Uno o varios estados; sin valor, todos."
    ),
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Citas que se cruzan con [start, end), ordenadas por inicio.

    Pide un rango (máximo 93 días, para la agenda) o un paciente (su historial)."""
    _ensure_aware(start, "start")
    _ensure_aware(end, "end")

    if (start is None) != (end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Indica el inicio y el fin del rango.",
        )
    if start is None and patient_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Indica un rango de fechas o un paciente.",
        )

    query = _clinic_appointments(db, clinic_id)

    if start is not None:
        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="El fin del rango debe ser posterior al inicio.",
            )
        if end - start > timedelta(days=MAX_RANGE_DAYS):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"El rango no puede superar {MAX_RANGE_DAYS} días.",
            )
        query = query.filter(
            Appointment.starts_at < end,
            func.appointment_end(Appointment.starts_at, Appointment.duration_minutes) > start,
        )

    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)
    if status_filter:
        query = query.filter(Appointment.status.in_([s.value for s in status_filter]))

    return query.order_by(Appointment.starts_at, Appointment.id).all()


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    return _get_clinic_appointment(db, appointment_id, clinic_id)


@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Agenda una cita «Programada» (ODON-134). La clínica sale del token."""
    _ensure_schedulable_patient(db, data.patient_id, clinic_id)
    doctor = ensure_assignable_doctor(db, data.doctor_id, clinic_id)
    ensure_not_in_past(data.starts_at)
    ensure_no_overlap(
        db,
        doctor_id=data.doctor_id,
        patient_id=data.patient_id,
        starts_at=data.starts_at,
        duration_minutes=data.duration_minutes,
    )
    # Al final: los errores que bloquean se muestran antes que el aviso.
    ensure_within_schedule(
        db,
        doctor=doctor,
        starts_at=data.starts_at,
        duration_minutes=data.duration_minutes,
        allow_outside=data.allow_outside_schedule,
    )

    appointment = Appointment(
        **data.model_dump(exclude={"allow_outside_schedule"}),
        clinic_id=clinic_id,
        status=AppointmentStatus.SCHEDULED.value,
        created_by_user_id=current_user.id,
    )
    appointment.status_changes.append(
        status_change(appointment, None, appointment.status, current_user.id)
    )
    db.add(appointment)
    commit_appointment(db, lambda: audit_service.record(
        db, current_user, "appointment.created", "appointment", appointment.id,
        patient_id=data.patient_id,
        detail=f"patient_id={data.patient_id} doctor_id={data.doctor_id}",
    ))
    return _get_clinic_appointment(db, appointment.id, clinic_id)


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: int,
    changes: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Reprograma doctor, horario, duración o motivo de una cita pendiente."""
    appointment = _get_clinic_appointment(db, appointment_id, clinic_id)

    if appointment.status not in PENDING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden modificar citas programadas o confirmadas.",
        )

    data = changes.model_dump(exclude_unset=True)
    allow_outside = data.pop("allow_outside_schedule", False)
    for required in ("doctor_id", "starts_at", "duration_minutes"):
        if required in data and data[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Doctor, inicio y duración son obligatorios.",
            )

    changed = [field for field, value in data.items() if getattr(appointment, field) != value]
    if not changed:
        return appointment

    doctor = appointment.doctor
    if "doctor_id" in changed:
        doctor = ensure_assignable_doctor(db, data["doctor_id"], clinic_id)
    if "starts_at" in changed:
        ensure_not_in_past(data["starts_at"])
    if {"doctor_id", "starts_at", "duration_minutes"} & set(changed):
        if appointment.patient.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El paciente está archivado. Reactívalo para agendarle citas.",
            )
        ensure_no_overlap(
            db,
            doctor_id=data.get("doctor_id", appointment.doctor_id),
            patient_id=appointment.patient_id,
            starts_at=data.get("starts_at", appointment.starts_at),
            duration_minutes=data.get("duration_minutes", appointment.duration_minutes),
            exclude_id=appointment.id,
        )
        ensure_within_schedule(
            db,
            doctor=doctor,
            starts_at=data.get("starts_at", appointment.starts_at),
            duration_minutes=data.get("duration_minutes", appointment.duration_minutes),
            allow_outside=allow_outside,
        )

    for field in changed:
        setattr(appointment, field, data[field])
    commit_appointment(db, lambda: audit_service.record(
        db, current_user, "appointment.updated", "appointment", appointment.id,
        patient_id=appointment.patient_id, fields=changed,
        detail=f"fields={','.join(sorted(changed))}",
    ))
    db.expire_all()
    return _get_clinic_appointment(db, appointment_id, clinic_id)


@router.post("/{appointment_id}/status", response_model=AppointmentResponse)
def change_appointment_status(
    appointment_id: int,
    data: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Confirma, cancela, marca atendida o no asistió, o reactiva (ODON-147).

    Repetir el estado actual no cambia nada ni agrega historial."""
    appointment = _get_clinic_appointment(db, appointment_id, clinic_id)
    new_status = data.status.value
    previous = appointment.status

    if new_status == previous:
        return appointment

    ensure_transition_allowed(appointment, new_status)

    if previous == AppointmentStatus.CANCELLED.value:
        # Reactivar: vuelve a ocupar el horario, así que se valida como una cita nueva.
        if appointment.patient.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El paciente está archivado. Reactívalo para agendarle citas.",
            )
        ensure_assignable_doctor(db, appointment.doctor_id, clinic_id)
        ensure_not_in_past(appointment.starts_at)
        ensure_no_overlap(
            db,
            doctor_id=appointment.doctor_id,
            patient_id=appointment.patient_id,
            starts_at=appointment.starts_at,
            duration_minutes=appointment.duration_minutes,
            exclude_id=appointment.id,
        )

    appointment.status = new_status
    appointment.status_changes.append(
        status_change(appointment, previous, new_status, current_user.id, data.note)
    )
    commit_appointment(db, lambda: audit_service.record(
        db, current_user, "appointment.status_changed", "appointment", appointment.id,
        patient_id=appointment.patient_id, fields=["status"],
        detail=f"from={previous} to={new_status}",
    ))
    db.expire_all()
    return _get_clinic_appointment(db, appointment_id, clinic_id)


@router.get("/{appointment_id}/history", response_model=list[AppointmentStatusChangeResponse])
def get_appointment_history(
    appointment_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Cambios de estado de la cita, del más antiguo al más reciente."""
    _get_clinic_appointment(db, appointment_id, clinic_id)
    return (
        db.query(AppointmentStatusChange)
        .options(joinedload(AppointmentStatusChange.changed_by))
        .filter(
            AppointmentStatusChange.appointment_id == appointment_id,
            AppointmentStatusChange.clinic_id == clinic_id,
        )
        .order_by(AppointmentStatusChange.id)
        .all()
    )
