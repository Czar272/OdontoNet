from pydantic import BaseModel
from datetime import date


class PatientCreate(BaseModel):

    first_name: str
    last_name: str
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class PatientResponse(BaseModel):

    id: int
    first_name: str
    last_name: str
    birth_date: date | None
    phone: str | None
    email: str | None
    address: str | None

    class Config:
        orm_mode = True
