from sqlalchemy import Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Patient(Base):
    """Paciente de una clínica. El doctor asignado es opcional (organiza el
    trabajo, no restringe el acceso) y, si existe, es de la misma clínica."""

    __tablename__ = "patients"
    __table_args__ = (
        # El correo es único dentro de cada clínica, no en todo el sistema.
        UniqueConstraint("clinic_id", "email", name="uq_patients_clinic_email"),
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

    doctor = relationship("Doctor", back_populates="patients", foreign_keys=[doctor_id])
    clinic = relationship("Clinic", back_populates="patients", foreign_keys=[clinic_id])
