"""Indicadores operativos de la clínica (ODON-202).

Todo se calcula sobre la clínica del token y se agrupa por fechas de la zona
horaria de la clínica. Los indicadores son conteos y tasas agregadas: no
devuelven contenido del expediente, por eso los ven los tres roles. La agenda
de hoy sí lista citas (paciente, doctor, hora), como la agenda compartida.

Periodo: `date_from` y `date_to` son fechas locales inclusivas; se convierten a
[date_from 00:00, date_to + 1 día 00:00) en la zona de la clínica.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment, AppointmentStatus
from app.models.availability import DoctorAvailabilityBlock
from app.models.clinic import Clinic
from app.models.clinical_visit import ClinicalVisit
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.patient_image import PatientImage
from app.models.periodontal import PeriodontalExam
from app.models.treatment import Treatment, TreatmentStatusChange
from app.models.user import User

# Un periodo largo vuelve costoso el cálculo de ocupación (un recorrido por día).
MAX_PERIOD_DAYS = 400

# Estados que ocupan el horario del doctor (mismos que impiden cruces).
BOOKED_STATUSES = (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value, AppointmentStatus.COMPLETED.value)


@dataclass
class Period:
    date_from: date
    date_to: date
    zone: ZoneInfo

    @property
    def start(self) -> datetime:
        return local_midnight(self.date_from, self.zone)

    @property
    def end(self) -> datetime:
        return local_midnight(self.date_to + timedelta(days=1), self.zone)

    def days(self) -> list[date]:
        return [self.date_from + timedelta(days=i) for i in range((self.date_to - self.date_from).days + 1)]


def local_midnight(day: date, zone: ZoneInfo) -> datetime:
    """00:00 local de un día, en UTC. Sumar días a las fechas locales (no al
    instante UTC) respeta los cambios de horario de verano de la zona."""
    return datetime.combine(day, time.min, zone).astimezone(timezone.utc)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def clinic_zone(db: Session, clinic_id: int) -> ZoneInfo:
    return ZoneInfo(db.get(Clinic, clinic_id).timezone)


def resolve_period(db: Session, clinic_id: int, date_from: Optional[date], date_to: Optional[date]) -> Period:
    """Por defecto, el mes en curso en la zona de la clínica."""
    zone = clinic_zone(db, clinic_id)
    today = datetime.now(timezone.utc).astimezone(zone).date()
    if date_from is None:
        date_from = today.replace(day=1)
    if date_to is None:
        next_month = (date_from.replace(day=28) + timedelta(days=4)).replace(day=1)
        date_to = next_month - timedelta(days=1)
    if date_to < date_from:
        raise _unprocessable("La fecha final no puede ser anterior a la inicial.")
    if (date_to - date_from).days + 1 > MAX_PERIOD_DAYS:
        raise _unprocessable(f"El periodo no puede superar {MAX_PERIOD_DAYS} días.")
    return Period(date_from, date_to, zone)


def resolve_doctor(db: Session, clinic_id: int, doctor_id: Optional[int]) -> Optional[Doctor]:
    if doctor_id is None:
        return None
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.user))
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic_id)
        .first()
    )
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor no encontrado.")
    return doctor


def _rate(part: int, total: int) -> Optional[float]:
    return round(100 * part / total, 1) if total else None


def _count(db: Session, statement) -> int:
    return db.execute(statement).scalar() or 0


def _appointments_between(clinic_id: int, start: datetime, end: datetime, doctor: Optional[Doctor]):
    conditions = [Appointment.clinic_id == clinic_id, Appointment.starts_at >= start, Appointment.starts_at < end]
    if doctor is not None:
        conditions.append(Appointment.doctor_id == doctor.id)
    return and_(*conditions)


def _occupancy(db: Session, clinic_id: int, period: Period, doctor: Optional[Doctor]) -> Optional[float]:
    """Minutos citados (programada, confirmada, atendida) sobre minutos de horario.

    Numerador y denominador cubren los mismos doctores: los activos con horario.
    Las citas de un doctor sin horario no cuentan (no hay base contra la cual
    medirlas). Las citas fuera del horario sí cuentan, así que puede pasar de 100 %.
    """
    blocks_query = db.query(DoctorAvailabilityBlock).join(
        Doctor, Doctor.id == DoctorAvailabilityBlock.doctor_id
    ).join(User, User.id == Doctor.user_id).filter(
        DoctorAvailabilityBlock.clinic_id == clinic_id, User.is_active.is_(True)
    )
    if doctor is not None:
        blocks_query = blocks_query.filter(DoctorAvailabilityBlock.doctor_id == doctor.id)
    minutes_by_weekday: dict[int, int] = {}
    doctor_ids: set[int] = set()
    for block in blocks_query.all():
        doctor_ids.add(block.doctor_id)
        minutes = (datetime.combine(date.min, block.end_time) - datetime.combine(date.min, block.start_time)).seconds // 60
        minutes_by_weekday[block.weekday] = minutes_by_weekday.get(block.weekday, 0) + minutes
    available = sum(minutes_by_weekday.get(day.weekday(), 0) for day in period.days())
    if not available:
        return None
    booked = _count(db, select(func.coalesce(func.sum(Appointment.duration_minutes), 0)).where(
        _appointments_between(clinic_id, period.start, period.end, doctor),
        Appointment.status.in_(BOOKED_STATUSES),
        Appointment.doctor_id.in_(doctor_ids),
    ))
    return round(100 * booked / available, 1)


def indicators(db: Session, clinic_id: int, period: Period, doctor: Optional[Doctor]) -> dict:
    zone = period.zone
    today = datetime.now(timezone.utc).astimezone(zone).date()
    today_start, today_end = local_midnight(today, zone), local_midnight(today + timedelta(days=1), zone)
    week_start_date = today - timedelta(days=today.weekday())
    week_start = local_midnight(week_start_date, zone)
    week_end = local_midnight(week_start_date + timedelta(days=7), zone)

    patients = select(func.count()).select_from(Patient).where(Patient.clinic_id == clinic_id)
    if doctor is not None:
        patients = patients.where(Patient.doctor_id == doctor.id)
    patients_active = _count(db, patients.where(Patient.archived_at.is_(None)))
    patients_new = _count(db, patients.where(Patient.created_at >= period.start, Patient.created_at < period.end))

    not_cancelled = Appointment.status != AppointmentStatus.CANCELLED.value
    appointments_today = _count(db, select(func.count()).select_from(Appointment).where(
        _appointments_between(clinic_id, today_start, today_end, doctor), not_cancelled))
    appointments_week = _count(db, select(func.count()).select_from(Appointment).where(
        _appointments_between(clinic_id, week_start, week_end, doctor), not_cancelled))

    by_status = dict(db.execute(
        select(Appointment.status, func.count()).where(
            _appointments_between(clinic_id, period.start, period.end, doctor)
        ).group_by(Appointment.status)
    ).all())
    completed = by_status.get(AppointmentStatus.COMPLETED.value, 0)
    no_show = by_status.get(AppointmentStatus.NO_SHOW.value, 0)
    cancelled = by_status.get(AppointmentStatus.CANCELLED.value, 0)
    total = sum(by_status.values())

    visits = select(func.count()).select_from(ClinicalVisit).where(
        ClinicalVisit.clinic_id == clinic_id, ClinicalVisit.voided_at.is_(None),
        ClinicalVisit.visit_at >= period.start, ClinicalVisit.visit_at < period.end,
    )
    if doctor is not None:
        visits = visits.where(ClinicalVisit.doctor_id == doctor.id)

    treatments = select(func.count()).select_from(TreatmentStatusChange).join(
        Treatment, Treatment.id == TreatmentStatusChange.treatment_id
    ).where(
        Treatment.clinic_id == clinic_id, TreatmentStatusChange.to_status == "completed",
        TreatmentStatusChange.changed_at >= period.start, TreatmentStatusChange.changed_at < period.end,
    )
    if doctor is not None:
        # El doctor de un tratamiento completado es el de la consulta en que se realizó.
        treatments = treatments.join(ClinicalVisit, ClinicalVisit.id == Treatment.completed_visit_id).where(
            ClinicalVisit.doctor_id == doctor.id
        )

    exams = select(func.count()).select_from(PeriodontalExam).where(
        PeriodontalExam.clinic_id == clinic_id, PeriodontalExam.voided_at.is_(None),
        PeriodontalExam.finalized_at >= period.start, PeriodontalExam.finalized_at < period.end,
    )
    images = select(func.count()).select_from(PatientImage).where(
        PatientImage.clinic_id == clinic_id, PatientImage.voided_at.is_(None),
        PatientImage.uploaded_at >= period.start, PatientImage.uploaded_at < period.end,
    )
    if doctor is not None:
        exams = exams.where(PeriodontalExam.created_by_user_id == doctor.user_id)
        images = images.where(PatientImage.uploaded_by_user_id == doctor.user_id)

    return {
        "patients_active": patients_active,
        "patients_new": patients_new,
        "appointments_today": appointments_today,
        "appointments_week": appointments_week,
        "appointments_period": total,
        "attendance_rate": _rate(completed, completed + no_show),
        "no_show_rate": _rate(no_show, completed + no_show),
        "cancellation_rate": _rate(cancelled, total),
        "visits_registered": _count(db, visits),
        "treatments_completed": _count(db, treatments),
        "periodontal_finalized": _count(db, exams),
        "images_uploaded": _count(db, images),
        "occupancy_rate": _occupancy(db, clinic_id, period, doctor),
    }


def agenda_today(db: Session, clinic_id: int, zone: ZoneInfo, doctor: Optional[Doctor]) -> list[dict]:
    today = datetime.now(timezone.utc).astimezone(zone).date()
    start, end = local_midnight(today, zone), local_midnight(today + timedelta(days=1), zone)
    rows = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor).joinedload(Doctor.user))
        .filter(
            _appointments_between(clinic_id, start, end, doctor),
            Appointment.status != AppointmentStatus.CANCELLED.value,
        )
        .order_by(Appointment.starts_at, Appointment.id)
        .all()
    )
    return [
        {
            "id": row.id,
            "starts_at": row.starts_at,
            "duration_minutes": row.duration_minutes,
            "status": row.status,
            "patient": {"id": row.patient.id, "name": f"{row.patient.first_name} {row.patient.last_name}"},
            "doctor": {"id": row.doctor.id, "name": row.doctor.user.name},
        }
        for row in rows
    ]


def dashboard(db: Session, clinic_id: int, date_from: Optional[date], date_to: Optional[date],
              doctor_id: Optional[int]) -> dict:
    period = resolve_period(db, clinic_id, date_from, date_to)
    doctor = resolve_doctor(db, clinic_id, doctor_id)
    return {
        "date_from": period.date_from,
        "date_to": period.date_to,
        "timezone": str(period.zone),
        "doctor_id": doctor.id if doctor else None,
        "indicators": indicators(db, clinic_id, period, doctor),
        "agenda_today": agenda_today(db, clinic_id, period.zone, doctor),
    }
