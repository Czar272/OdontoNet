from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.dependencies import get_db
from app.auth.jwt_handler import decode_token
from app.models.user import User

# auto_error=False: la falta de token se responde con 401 (no 403).
security = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:

    if credentials is None:
        raise _unauthorized("No autenticado.")

    payload = decode_token(credentials.credentials)

    if not payload:
        raise _unauthorized("Token inválido o expirado.")

    email = payload.get("sub")

    user = db.query(User).filter(User.email == email).first()

    if not user or user.is_active is False:
        raise _unauthorized("Usuario no encontrado o inactivo.")

    # Un cambio de contraseña cierra las sesiones abiertas antes (ODON-54).
    if user.password_changed_at is not None:
        issued_at = payload.get("iat")
        if not isinstance(issued_at, (int, float)) or issued_at < user.password_changed_at.timestamp():
            raise _unauthorized("Tu contraseña cambió. Inicia sesión de nuevo.")

    return user


def get_current_clinic_id(current_user: User = Depends(get_current_user)) -> int:
    """Clínica del usuario autenticado.

    Es la única fuente válida de clinic_id: nunca se toma del cuerpo,
    la URL ni los parámetros enviados por el cliente.
    """
    return current_user.clinic_id
