"""Reglas de negocio para la gestión de usuarios por administración (ODON-86)."""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.permissions import CLINICAL_PROFILE_ROLES
from app.auth.security import hash_password
from app.models.doctor import Doctor
from app.models.user import User
from app.services import password_service
from app.schemas.user_schema import UserCreate, UserUpdate


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _email_taken(db: Session, email: str, exclude_user_id: Optional[int] = None) -> bool:
    # El correo es único en todo el sistema porque identifica el inicio de sesión.
    query = db.query(User.id).filter(User.email == email)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None


def get_clinic_user(db: Session, user_id: int, clinic_id: int) -> User:
    """Usuario de la clínica indicada; 404 si no existe o es de otra clínica."""
    user = db.query(User).filter(User.id == user_id, User.clinic_id == clinic_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    return user


def create_user(db: Session, data: UserCreate, clinic_id: int) -> User:
    if _email_taken(db, data.email):
        raise _conflict("Ya existe un usuario con ese correo.")

    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role.value,
        clinic_id=clinic_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, data: UserUpdate, acting_admin: User) -> User:
    # Un campo enviado como null se trata como no enviado: ninguno admite vacío.
    changes = {key: value for key, value in data.model_dump(exclude_unset=True).items() if value is not None}

    if "password" in changes and user.id == acting_admin.id:
        # Cerraría la propia sesión; el cambio propio pide la contraseña actual.
        raise _conflict("Para cambiar tu propia contraseña usa «Cambiar contraseña».")

    if "email" in changes and changes["email"] != user.email:
        if _email_taken(db, changes["email"], exclude_user_id=user.id):
            raise _conflict("Ya existe un usuario con ese correo.")
        user.email = changes["email"]

    if "role" in changes and changes["role"].value != user.role:
        new_role = changes["role"].value
        if user.id == acting_admin.id:
            # Evita que la clínica se quede sin administrador.
            raise _conflict("No puedes cambiar tu propio rol.")
        has_profile = db.query(Doctor.id).filter(Doctor.user_id == user.id).first() is not None
        if has_profile and new_role not in CLINICAL_PROFILE_ROLES:
            raise _conflict("El usuario tiene un perfil de doctor; solo puede tener rol doctor o administración.")
        user.role = new_role

    if "name" in changes:
        user.name = changes["name"]

    if "password" in changes:
        # Cierra las sesiones del usuario y anula sus enlaces de recuperación.
        password_service.set_password_by_admin(db, user, changes["password"])

    db.commit()
    db.refresh(user)
    return user


def set_user_active(db: Session, user: User, active: bool, acting_admin: User) -> User:
    """Activa o desactiva un usuario sin borrar nada (ODON-94).

    Un usuario inactivo no inicia sesión y su token deja de funcionar en la
    siguiente petición, porque get_current_user revisa is_active cada vez.
    Sus registros (pacientes asignados, perfil de doctor) se conservan."""
    if not active and user.id == acting_admin.id:
        raise _conflict("No puedes desactivar tu propia cuenta.")

    if user.is_active is not active:
        user.is_active = active
        db.commit()
        db.refresh(user)
    return user
