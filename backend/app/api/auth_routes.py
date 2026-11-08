from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.user_schema import (
    CurrentUserResponse,
    MessageResponse,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.auth.security import verify_password
from app.auth.jwt_handler import create_access_token, token_lifetime
from app.auth.dependencies import get_current_user
from app.auth.permissions import Role, require_roles
from app.services import email_service, password_service, rate_limit_service, user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    """Un administrador crea un usuario en su propia clínica.

    Equivale a POST /users/, que es la ruta que usa el frontend."""

    return user_service.create_user(db, user, admin.clinic_id)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={429: {"description": "Demasiados intentos fallidos (incluye Retry-After)."}},
)
def login_user(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    # Límite de intentos (ODON-230): se revisa antes de verificar la contraseña.
    limit = rate_limit_service.login_limit()
    ip = rate_limit_service.client_ip(request)
    rate_limit_service.ensure_allowed(db, limit, ip, user.email)

    db_user = db.query(User).filter(User.email == user.email).first()
    valid_password = db_user is not None and verify_password(user.password, db_user.hashed_password)

    # Un usuario desactivado no obtiene token; mismo mensaje para no revelar el motivo.
    if not valid_password or db_user.is_active is False:
        rate_limit_service.record(db, limit, ip, user.email)
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    rate_limit_service.clear_account(db, limit, user.email)
    return _token_response(db_user, user.remember_me)


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .options(joinedload(User.clinic))
        .filter(User.id == current_user.id)
        .first()
    )

    return user


def _token_response(user: User, remember_me: bool) -> dict:
    access_token = create_access_token(
        {"sub": user.email, "role": user.role}, remember_me=remember_me
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": int(token_lifetime(remember_me).total_seconds()),
    }


# Mismo mensaje exista o no la cuenta: no se revela qué correos están registrados.
RESET_REQUESTED = "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Envía un enlace de recuperación si el correo pertenece a una cuenta activa.

    Responde igual en todos los casos; el correo sale en segundo plano. Cada IP
    tiene un límite de solicitudes (ODON-230), además del límite por cuenta."""
    limit = rate_limit_service.reset_request_limit()
    ip = rate_limit_service.client_ip(request)
    rate_limit_service.ensure_allowed(db, limit, ip)
    rate_limit_service.record(db, limit, ip)
    result = password_service.request_reset(db, data.email)
    if result is not None:
        email, link = result
        background_tasks.add_task(
            email_service.send_email,
            email,
            "Restablece tu contraseña de OdontoNet",
            password_service.reset_email_body(link),
        )
    return {"message": RESET_REQUESTED}


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(data: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    """Fija una contraseña nueva con un enlace válido. Cierra todas las sesiones.

    Los enlaces inválidos cuentan para un límite por IP (ODON-230)."""
    limit = rate_limit_service.reset_confirm_limit()
    ip = rate_limit_service.client_ip(request)
    rate_limit_service.ensure_allowed(db, limit, ip)
    try:
        password_service.confirm_reset(db, data.token, data.new_password)
    except HTTPException:
        db.rollback()
        rate_limit_service.record(db, limit, ip)
        raise
    return {"message": "Tu contraseña se actualizó. Inicia sesión con la nueva."}


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambia la contraseña del usuario autenticado.

    Cierra las demás sesiones y devuelve un token nuevo para seguir en esta.
    Una contraseña actual incorrecta cuenta como fallo de inicio de sesión
    (ODON-230): con un token robado no se puede adivinar sin límite."""
    limit = rate_limit_service.login_limit()
    ip = rate_limit_service.client_ip(request)
    email = current_user.email
    rate_limit_service.ensure_allowed(db, limit, ip, email)
    try:
        user = password_service.change_password(
            db, current_user, data.current_password, data.new_password
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            db.rollback()
            rate_limit_service.record(db, limit, ip, email)
        raise
    return _token_response(user, data.remember_me)
