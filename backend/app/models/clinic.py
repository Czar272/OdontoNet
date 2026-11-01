from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Clinic(Base):
    """Límite de aislamiento: todo usuario, doctor y paciente pertenece a una clínica."""

    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    email = Column(String)

    # passive_deletes="all": una clínica con datos no se puede borrar; las FK
    # NOT NULL lo impiden y el ORM no intenta dejar registros sin clínica.
    users = relationship(
        "User", back_populates="clinic", foreign_keys="User.clinic_id", passive_deletes="all"
    )
    doctors = relationship(
        "Doctor", back_populates="clinic", foreign_keys="Doctor.clinic_id", passive_deletes="all"
    )
    patients = relationship(
        "Patient", back_populates="clinic", foreign_keys="Patient.clinic_id", passive_deletes="all"
    )
