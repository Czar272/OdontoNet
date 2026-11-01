from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.user_schema import (
    CurrentUserResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.auth.security import verify_password
from app.auth.jwt_handler import create_access_token
from app.auth.dependencies import get_current_user
from app.auth.permissions import Role, require_roles
from app.services import user_service

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


@router.post("/login", response_model=TokenResponse)
def login_user(user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    valid_password = verify_password(user.password, db_user.hashed_password)

    # Un usuario desactivado no obtiene token; mismo mensaje para no revelar el motivo.
    if not valid_password or db_user.is_active is False:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    access_token = create_access_token({"sub": db_user.email, "role": db_user.role})

    return {"access_token": access_token, "token_type": "bearer"}


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
