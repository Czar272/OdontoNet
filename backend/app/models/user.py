from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database.connection import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship


class User(Base):

    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="doctor")
    is_active = Column(Boolean, default=True)
    doctor_profile = relationship("Doctor", back_populates="user", uselist=False)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    clinic = relationship("Clinic", back_populates="users")
