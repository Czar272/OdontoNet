from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_clinic_id, get_current_user
from app.auth.permissions import ALL_ROLES, Role, require_roles
from app.database.dependencies import get_db
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.clinic_schema import ClinicResponse, ClinicUpdate
from app.services import audit_service

# Datos de la clínica de la sesión: todos los roles consultan, solo
# administración edita (docs/PERMISSIONS.md). No hay rutas con id: un usuario
# nunca puede apuntar a otra clínica.
router = APIRouter(
    prefix="/clinic",
    tags=["Clinic"],
    dependencies=[Depends(require_roles(*ALL_ROLES))],
)


def _current_clinic(db: Session, clinic_id: int) -> Clinic:
    clinic = db.get(Clinic, clinic_id)
    if clinic is None:  # No debería ocurrir: users.clinic_id es FK obligatoria.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clínica no encontrada.")
    return clinic


@router.get("", response_model=ClinicResponse)
def get_clinic(
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Datos de la clínica del usuario autenticado."""
    return _current_clinic(db, clinic_id)


@router.patch(
    "",
    response_model=ClinicResponse,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def update_clinic(
    changes: ClinicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Edita nombre, dirección, teléfono, correo o zona horaria de la propia clínica."""
    clinic = _current_clinic(db, clinic_id)

    data = changes.model_dump(exclude_unset=True)
    if data.get("timezone", "") is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La zona horaria de la clínica es obligatoria.",
        )
    if "name" in data and data["name"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El nombre de la clínica es obligatorio.",
        )

    changed = [field for field, value in data.items() if getattr(clinic, field) != value]
    for field in changed:
        setattr(clinic, field, data[field])
    if changed:
        # Solo nombres de campos (ODON-222).
        audit_service.record(db, current_user, "clinic.updated", "clinic", clinic.id, fields=changed)
        db.commit()
    db.refresh(clinic)
    return clinic
