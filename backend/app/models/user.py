from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.connection import Base


class User(Base):

    __tablename__ = "users"
    # (id, clinic_id) es único para que doctors pueda referenciar ambos a la vez
    # y la base garantice que un perfil de doctor es de la clínica de su usuario.
    __table_args__ = (UniqueConstraint("id", "clinic_id", name="uq_users_id_clinic"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="doctor")
    is_active = Column(Boolean, default=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)

    clinic = relationship("Clinic", back_populates="users")
    # Uno a uno: un usuario tiene como máximo un perfil de doctor (uq_doctors_user_id).
    doctor_profile = relationship(
        "Doctor",
        back_populates="user",
        uselist=False,
        foreign_keys="Doctor.user_id",
        passive_deletes="all",
    )
