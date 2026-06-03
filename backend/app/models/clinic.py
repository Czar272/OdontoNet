from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Clinic(Base):

    __tablename__ = "clinics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    email = Column(String)
    users = relationship("User", back_populates="clinic")
    doctors = relationship("Doctor", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")
