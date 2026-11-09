from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, field_validator

from app.auth.permissions import Role
from app.core.password_policy import MAX_LENGTH, MIN_LENGTH, check_new_password
from app.schemas.clinic_schema import ClinicSimpleResponse

UserName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
# Contraseña nueva (ODON-230): al menos 10 caracteres y no una de las filtradas.
UserPassword = Annotated[str, StringConstraints(min_length=MIN_LENGTH, max_length=MAX_LENGTH)]


class UserCreate(BaseModel):
    """Alta de usuario por un administrador. La clínica se toma del
    administrador autenticado; no forma parte del contrato."""

    name: UserName
    email: EmailStr
    password: UserPassword
    role: Role = Role.DOCTOR

    _common = field_validator("password")(check_new_password)


class UserUpdate(BaseModel):
    """Edición parcial por un administrador: solo se cambian los campos
    enviados. La clínica no se puede cambiar y la contraseña nunca se
    devuelve; enviarla la restablece."""

    name: Optional[UserName] = None
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    password: Optional[UserPassword] = None

    @field_validator("password")
    def _common(cls, value):
        return value if value is None else check_new_password(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Segundos de validez del token de acceso; luego se renueva con la cookie.
    expires_in: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    # "Recuérdame": sesión de larga duración (REMEMBER_ME_EXPIRE_DAYS).
    remember_me: bool = False


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    new_password: UserPassword

    _common = field_validator("new_password")(check_new_password)


class PasswordChange(BaseModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    new_password: UserPassword

    _common = field_validator("new_password")(check_new_password)


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    clinic_id: int
    is_active: bool = True

    @field_validator("is_active", mode="before")
    def _null_is_active(cls, value):
        # Filas antiguas sin valor se consideran activas, igual que en el login.
        return True if value is None else value

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(BaseModel):

    id: int
    name: str
    email: str
    role: str
    clinic: ClinicSimpleResponse

    model_config = ConfigDict(from_attributes=True)
