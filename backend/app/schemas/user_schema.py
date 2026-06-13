from pydantic import BaseModel, EmailStr
from app.schemas.clinic_schema import ClinicSimpleResponse


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    clinic_id: int

    class Config:
        orm_mode = True


class CurrentUserResponse(BaseModel):

    id: int
    name: str
    email: str
    role: str
    clinic: ClinicSimpleResponse

    class Config:
        orm_mode = True
