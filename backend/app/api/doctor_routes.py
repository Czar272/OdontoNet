from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Query as QueryParam
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, joinedload

from app.auth.dependencies import get_current_clinic_id
from app.auth.permissions import ALL_ROLES, Role, require_roles
from app.database.dependencies import get_db
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.doctor_schema import DoctorCreate, DoctorResponse

# Todos los roles consultan doctores; solo administración crea perfiles (docs/PERMISSIONS.md).
router = APIRouter(
    prefix="/doctors",
    tags=["Doctors"],
    dependencies=[Depends(require_roles(*ALL_ROLES))],
)


def _clinic_doctors(db: Session, clinic_id: int) -> Query:
    return (
        db.query(Doctor)
        .options(joinedload(Doctor.user))
        .filter(Doctor.clinic_id == clinic_id)
    )


@router.post(
    "/",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def create_doctor(
    doctor: DoctorCreate,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    user = (
        db.query(User)
        .filter(User.id == doctor.user_id, User.clinic_id == clinic_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El usuario no pertenece a la clínica.",
        )

    if db.query(Doctor.id).filter(Doctor.user_id == user.id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene un perfil de doctor.",
        )

    new_doctor = Doctor(**doctor.dict(), clinic_id=clinic_id)
    db.add(new_doctor)
    try:
        db.commit()
    except IntegrityError:
        # Dos altas simultáneas: la restricción uq_doctors_user_id decide.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene un perfil de doctor.",
        )

    return _clinic_doctors(db, clinic_id).filter(Doctor.id == new_doctor.id).one()


@router.get("/", response_model=list[DoctorResponse])
def get_doctors(
    active: Optional[bool] = QueryParam(
        None,
        description="true: solo doctores activos; false: solo inactivos; sin valor: todos.",
    ),
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Doctores de la clínica con su nombre y especialidad, ordenados por nombre.

    Sin filtro se incluyen los inactivos, porque siguen apareciendo en el
    historial de pacientes; para asignar pacientes se usa active=true."""
    query = _clinic_doctors(db, clinic_id).join(Doctor.user)
    if active is True:
        query = query.filter(User.is_active.isnot(False))
    elif active is False:
        query = query.filter(User.is_active.is_(False))
    return query.order_by(User.name, Doctor.id).all()


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    doctor = _clinic_doctors(db, clinic_id).filter(Doctor.id == doctor_id).first()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor no encontrado."
        )

    return doctor
