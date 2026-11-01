from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_clinic_id
from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserResponse, UserUpdate
from app.services import user_service

# Gestión del personal: solo administración (docs/PERMISSIONS.md, users:manage).
router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(require_roles(Role.ADMIN))],
)


@router.get("/", response_model=list[UserResponse])
def list_users(
    role: Optional[Role] = Query(None, description="Filtra por rol."),
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    query = db.query(User).filter(User.clinic_id == clinic_id)
    if role is not None:
        query = query.filter(User.role == role.value)
    return query.order_by(User.name, User.id).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    return user_service.get_clinic_user(db, user_id, clinic_id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Crea un usuario en la clínica del administrador autenticado."""
    return user_service.create_user(db, data, clinic_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    """Edita nombre, correo, rol o contraseña de un usuario de la misma clínica."""
    user = user_service.get_clinic_user(db, user_id, admin.clinic_id)
    return user_service.update_user(db, user, data, acting_admin=admin)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    """Retira el acceso de un usuario conservando su historial."""
    user = user_service.get_clinic_user(db, user_id, admin.clinic_id)
    return user_service.set_user_active(db, user, False, acting_admin=admin)


@router.post("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    """Devuelve el acceso a un usuario desactivado."""
    user = user_service.get_clinic_user(db, user_id, admin.clinic_id)
    return user_service.set_user_active(db, user, True, acting_admin=admin)
