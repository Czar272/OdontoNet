"""Roles y control de acceso por rol (RBAC).

La matriz completa está documentada en docs/PERMISSIONS.md.
El rol se lee del usuario en base de datos (no del token), por lo que un
cambio de rol tiene efecto inmediato.
"""
from enum import Enum

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.models.user import User


class Role(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"


ALL_ROLES = (Role.ADMIN, Role.DOCTOR, Role.RECEPTIONIST)


def require_roles(*roles: Role):
    """Dependencia que permite el acceso solo a los roles indicados (403 si no)."""
    allowed = {role.value for role in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta acción.",
            )
        return current_user

    return dependency
