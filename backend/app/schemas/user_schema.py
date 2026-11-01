from pydantic import BaseModel, EmailStr, constr

from app.auth.permissions import Role
from app.schemas.clinic_schema import ClinicSimpleResponse


class UserCreate(BaseModel):
    """Alta de usuario por un administrador. La clínica se toma del
    administrador autenticado; no forma parte del contrato."""

    name: constr(strip_whitespace=True, min_length=1, max_length=120)
    email: EmailStr
    password: constr(min_length=8, max_length=128)
    role: Role = Role.DOCTOR


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
