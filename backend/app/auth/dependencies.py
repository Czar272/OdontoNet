from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.dependencies import get_db
from app.auth.jwt_handler import decode_token
from app.models.user import User

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:

    token = credentials.credentials

    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado"
        )

    email = payload.get("sub")

    user = db.query(User).filter(User.email == email).first()

    if not user or user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )

    return user


def get_current_clinic_id(current_user: User = Depends(get_current_user)) -> int:
    """Clínica del usuario autenticado.

    Es la única fuente válida de clinic_id: nunca se toma del cuerpo,
    la URL ni los parámetros enviados por el cliente.
    """
    return current_user.clinic_id
