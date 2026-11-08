from sqlalchemy import Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Patient(Base):
    """Paciente de una clínica. El doctor asignado es opcional (organiza el
    trabajo, no restringe el acceso) y, si existe, es de la misma clínica."""

    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patients_clinic_created_at", "clinic_id", "created_at"),
        # El correo es único dentro de cada clínica, no en todo el sistema.
        UniqueConstraint("clinic_id", "email", name="uq_patients_clinic_email"),
        # Permite que appointments referencie (patient_id, clinic_id) a la vez.
        UniqueConstraint("id", "clinic_id", name="uq_patients_id_clinic"),
        # El doctor asignado pertenece a la clínica del paciente (ODON-98).
        # Con doctor_id NULL la restricción no aplica: el doctor es opcional.
        ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_patients_doctor_clinic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    birth_date = Column(Date)
    phone = Column(String)
    email = Column(String)
    address = Column(String)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    # NULL = activo. Archivar conserva todos los datos y el historial (ODON-122).
    archived_at = Column(DateTime(timezone=True), nullable=True)
    # Fecha de alta en el sistema (ODON-202). Los pacientes creados antes de esta
    # columna quedan en NULL: no se inventa una fecha.
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())

    doctor = relationship("Doctor", back_populates="patients", foreign_keys=[doctor_id])
    clinic = relationship("Clinic", back_populates="patients", foreign_keys=[clinic_id])
    # Las citas son historial: un paciente con citas no se borra (se archiva).
    appointments = relationship(
        "Appointment",
        back_populates="patient",
        foreign_keys="Appointment.patient_id",
        passive_deletes="all",
    )
