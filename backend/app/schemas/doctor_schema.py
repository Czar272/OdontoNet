from pydantic import BaseModel
from app.schemas.user_schema import UserResponse


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
    user: UserResponse

    class Config:
        orm_mode = True
