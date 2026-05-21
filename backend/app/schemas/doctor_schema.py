from pydantic import BaseModel


class DoctorCreate(BaseModel):
    user_id: int
    specialization: str | None = None
    license_number: str | None = None
    phone: str | None = None


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    specialization: str | None
    license_number: str | None
    phone: str | None

    class Config:
        orm_mode = True
