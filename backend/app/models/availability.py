from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    Time,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base

WEEKDAY_LABELS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class DoctorAvailabilityBlock(Base):
    """Un bloque del horario semanal de un doctor (ODON-142).

    weekday: 0 = lunes … 6 = domingo (como date.weekday()). Las horas son la
    hora local de la clínica (Clinic.timezone)."""

    __tablename__ = "doctor_availability_blocks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_availability_doctor_clinic",
        ),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_weekday"),
        CheckConstraint("start_time < end_time", name="ck_availability_times"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    weekday = Column(SmallInteger, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    doctor = relationship("Doctor", back_populates="availability", foreign_keys=[doctor_id])
