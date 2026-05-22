from pydantic import BaseModel
from datetime import date
from app.schemas.doctor_schema import DoctorResponse


class PatientCreate(BaseModel):

    first_name: str
    last_name: str
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    doctor_id: int | None = None


class PatientResponse(BaseModel):

    id: int
    first_name: str
    last_name: str
    birth_date: date | None
    phone: str | None
    email: str | None
    address: str | None
    doctor_id: int | None = None
    doctor: DoctorResponse | None

    class Config:
        orm_mode = True
