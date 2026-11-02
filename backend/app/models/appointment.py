from datetime import timedelta
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import relationship

from app.database.connection import Base


class AppointmentStatus(str, Enum):
    """Estados de una cita (ODON-131). Las transiciones llegan en ODON-146."""

    SCHEDULED = "scheduled"  # Programada
    CONFIRMED = "confirmed"  # Confirmada
    COMPLETED = "completed"  # Atendida
    CANCELLED = "cancelled"  # Cancelada
    NO_SHOW = "no_show"  # No asistió


# Estados que ocupan el horario del doctor. Cancelada y No asistió lo liberan.
BLOCKING_STATUSES = (
    AppointmentStatus.SCHEDULED.value,
    AppointmentStatus.CONFIRMED.value,
    AppointmentStatus.COMPLETED.value,
)

MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 480

_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in AppointmentStatus)
_BLOCKING_VALUES = ", ".join(f"'{status}'" for status in BLOCKING_STATUSES)


class Appointment(Base):
    """Cita de un paciente con un doctor de la misma clínica.

    Se guarda el inicio (con zona horaria) y la duración en minutos. El fin se
    calcula con la función SQL appointment_end (ver migración c4f8a1d2e6b3).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        # Paciente y doctor son de la clínica de la cita.
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_appointments_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_appointments_doctor_clinic",
        ),
        CheckConstraint(
            f"duration_minutes BETWEEN {MIN_DURATION_MINUTES} AND {MAX_DURATION_MINUTES}",
            name="ck_appointments_duration",
        ),
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_appointments_status"),
        # Un doctor no tiene dos citas activas que se crucen, aunque lleguen
        # dos peticiones a la vez. Requiere la extensión btree_gist.
        ExcludeConstraint(
            ("doctor_id", "="),
            (
                text("tstzrange(starts_at, appointment_end(starts_at, duration_minutes), '[)')"),
                "&&",
            ),
            name="ex_appointments_doctor_overlap",
            using="gist",
            where=text(f"status IN ({_BLOCKING_VALUES})"),
        ),
        # Un paciente tampoco tiene dos citas activas que se crucen, aunque
        # sean con doctores distintos (ODON-134).
        ExcludeConstraint(
            ("patient_id", "="),
            (
                text("tstzrange(starts_at, appointment_end(starts_at, duration_minutes), '[)')"),
                "&&",
            ),
            name="ex_appointments_patient_overlap",
            using="gist",
            where=text(f"status IN ({_BLOCKING_VALUES})"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    status = Column(String, nullable=False, server_default=AppointmentStatus.SCHEDULED.value)
    # Motivo administrativo ("Limpieza", "Control"); las notas clínicas van en el expediente.
    reason = Column(String(255))
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    clinic = relationship("Clinic", back_populates="appointments", foreign_keys=[clinic_id])
    patient = relationship("Patient", back_populates="appointments", foreign_keys=[patient_id])
    doctor = relationship("Doctor", back_populates="appointments", foreign_keys=[doctor_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    @property
    def ends_at(self):
        """Fin de la cita; en SQL, appointment_end(starts_at, duration_minutes)."""
        if self.starts_at is None or self.duration_minutes is None:
            return None
        return self.starts_at + timedelta(minutes=self.duration_minutes)
