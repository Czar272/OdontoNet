from typing import Optional

from pydantic import BaseModel, EmailStr, constr, validator

from app.auth.permissions import Role
from app.schemas.clinic_schema import ClinicSimpleResponse

UserName = constr(strip_whitespace=True, min_length=1, max_length=120)
UserPassword = constr(min_length=8, max_length=128)


class UserCreate(BaseModel):
    """Alta de usuario por un administrador. La clínica se toma del
    administrador autenticado; no forma parte del contrato."""

    name: UserName
    email: EmailStr
    password: UserPassword
    role: Role = Role.DOCTOR


class UserUpdate(BaseModel):
    """Edición parcial por un administrador: solo se cambian los campos
    enviados. La clínica no se puede cambiar y la contraseña nunca se
    devuelve; enviarla la restablece."""

    name: Optional[UserName] = None
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    password: Optional[UserPassword] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Segundos de validez del token, para que el cliente sepa cuánto dura la sesión.
    expires_in: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    # "Recuérdame": token de larga duración (REMEMBER_ME_EXPIRE_DAYS).
    remember_me: bool = False


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: constr(strip_whitespace=True, min_length=1, max_length=200)
    new_password: UserPassword


class PasswordChange(BaseModel):
    current_password: constr(min_length=1, max_length=128)
    new_password: UserPassword
    # Conserva la duración de la sesión actual en el token nuevo.
    remember_me: bool = False


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    clinic_id: int
    is_active: bool = True

    @validator("is_active", pre=True)
    def _null_is_active(cls, value):
        # Filas antiguas sin valor se consideran activas, igual que en el login.
        return True if value is None else value

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
