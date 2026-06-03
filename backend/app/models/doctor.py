from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Doctor(Base):

    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    specialization = Column(String)
    license_number = Column(String)
    phone = Column(String)
    user = relationship("User", back_populates="doctor_profile")
    patients = relationship("Patient", back_populates="doctor")
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    clinic = relationship("Clinic", back_populates="doctors")
