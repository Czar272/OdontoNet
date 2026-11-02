from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Doctor(Base):
    """Perfil clínico de un usuario (relación uno a uno con User, ODON-78)."""

    __tablename__ = "doctors"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_doctors_user_id"),
        # Permite que patients referencie (doctor_id, clinic_id) a la vez.
        UniqueConstraint("id", "clinic_id", name="uq_doctors_id_clinic"),
        # El perfil pertenece a la misma clínica que su usuario.
        ForeignKeyConstraint(
            ["user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_doctors_user_clinic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    specialization = Column(String)
    license_number = Column(String)
    phone = Column(String)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)

    user = relationship("User", back_populates="doctor_profile", foreign_keys=[user_id])
    # passive_deletes="all": el ORM no pone doctor_id en NULL al borrar; la FK
    # lo impide y el historial de pacientes se conserva.
    patients = relationship(
        "Patient",
        back_populates="doctor",
        foreign_keys="Patient.doctor_id",
        passive_deletes="all",
    )
    clinic = relationship("Clinic", back_populates="doctors", foreign_keys=[clinic_id])
    # Las citas se conservan: un doctor con citas no se borra.
    appointments = relationship(
        "Appointment",
        back_populates="doctor",
        foreign_keys="Appointment.doctor_id",
        passive_deletes="all",
    )
