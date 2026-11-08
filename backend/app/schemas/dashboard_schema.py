"""Panel de inicio: indicadores de la clínica (ODON-202)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class PersonRef(BaseModel):
    id: int
    name: str


class DashboardIndicators(BaseModel):
    patients_active: int
    # Solo cuenta pacientes con fecha de alta (los anteriores a ODON-202 no la tienen).
    patients_new: int
    appointments_today: int
    appointments_week: int
    appointments_period: int
    # Porcentajes 0–100 con un decimal; null si no hay base para calcularlos.
    attendance_rate: Optional[float]
    no_show_rate: Optional[float]
    cancellation_rate: Optional[float]
    visits_registered: int
    treatments_completed: int
    periodontal_finalized: int
    images_uploaded: int
    occupancy_rate: Optional[float]


class AgendaItem(BaseModel):
    id: int
    starts_at: datetime
    duration_minutes: int
    status: str
    patient: PersonRef
    doctor: PersonRef


class DashboardRead(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    doctor_id: Optional[int]
    indicators: DashboardIndicators
    agenda_today: list[AgendaItem]
