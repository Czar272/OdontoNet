from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint
from app.database.connection import Base
from sqlalchemy.orm import relationship


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        # El correo es único dentro de cada clínica, no en todo el sistema.
        UniqueConstraint("clinic_id", "email", name="uq_patients_clinic_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    birth_date = Column(Date)
    phone = Column(String)
    email = Column(String)
    address = Column(String)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    doctor = relationship("Doctor", back_populates="patients")
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    clinic = relationship("Clinic", back_populates="patients")
