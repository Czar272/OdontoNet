from sqlalchemy import Column, Integer, String, Date, ForeignKey
from app.database.connection import Base
from sqlalchemy.orm import relationship


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    birth_date = Column(Date)
    phone = Column(String)
    email = Column(String, unique=True)
    address = Column(String)
    assigned_doctor = Column(String, nullable=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    doctor = relationship("Doctor", back_populates="patients")
