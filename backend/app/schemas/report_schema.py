"""Reportes de citas y pacientes (ODON-206)."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel

from app.schemas.dashboard_schema import PersonRef

Grouping = Literal["day", "week", "month"]


class StatusCounts(BaseModel):
    scheduled: int
    confirmed: int
    completed: int
    cancelled: int
    no_show: int
    total: int
    # Sobre atendidas + no asistió; null sin base.
    attendance_rate: Optional[float] = None
    no_show_rate: Optional[float] = None


class Bucket(BaseModel):
    # Recortado al periodo; partial = el grupo (semana o mes) no está completo.
    period_start: date
    period_end: date
    partial: bool


class AppointmentBucket(StatusCounts, Bucket):
    pass


class DoctorAppointments(StatusCounts):
    doctor: PersonRef


class AppointmentsReport(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    group: Grouping
    doctor_id: Optional[int] = None
    series: list[AppointmentBucket]
    by_doctor: list[DoctorAppointments]
    totals: StatusCounts


class PatientBucket(Bucket):
    new_patients: int


class PatientsReport(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    group: Grouping
    doctor_id: Optional[int] = None
    series: list[PatientBucket]
    total_new: int
    # Pacientes sin fecha de alta (registrados antes de ODON-202).
    without_registration_date: int
