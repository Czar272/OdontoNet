import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Query as QueryParam
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, joinedload

from app.auth.dependencies import get_current_clinic_id, get_current_user
from app.auth.permissions import ALL_ROLES, CLINICAL_PROFILE_ROLES, Role, require_roles
from app.database.dependencies import get_db
from app.models.availability import DoctorAvailabilityBlock
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.availability_schema import AvailabilityUpdate, DoctorAvailabilityResponse
from app.schemas.doctor_schema import DoctorCreate, DoctorResponse, DoctorUpdate

audit_logger = logging.getLogger("odontonet.audit")

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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El usuario no pertenece a la clínica.",
        )

    if user.role not in CLINICAL_PROFILE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Solo un usuario con rol doctor o administración puede tener perfil de doctor.",
        )

    if db.query(Doctor.id).filter(Doctor.user_id == user.id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene un perfil de doctor.",
        )

    new_doctor = Doctor(**doctor.model_dump(), clinic_id=clinic_id)
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


# --- Disponibilidad (ODON-142) ------------------------------------------------------
# Rutas antes de /{doctor_id} para que "availability" no se tome como id.


def _availability(doctor: Doctor, timezone: str) -> dict:
    return {"doctor_id": doctor.id, "timezone": timezone, "blocks": doctor.availability}


def _clinic_timezone(db: Session, clinic_id: int) -> str:
    return db.query(Clinic.timezone).filter(Clinic.id == clinic_id).scalar()


@router.get("/availability", response_model=list[DoctorAvailabilityResponse])
def get_clinic_availability(
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Horario semanal de todos los doctores de la clínica (para la agenda).

    Un doctor sin bloques no tiene horario registrado: se agenda libremente."""
    timezone = _clinic_timezone(db, clinic_id)
    doctors = (
        _clinic_doctors(db, clinic_id)
        .options(joinedload(Doctor.availability))
        .order_by(Doctor.id)
        .all()
    )
    return [_availability(doctor, timezone) for doctor in doctors]


@router.get("/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
def get_doctor_availability(
    doctor_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    doctor = _get_clinic_doctor(db, doctor_id, clinic_id)
    return _availability(doctor, _clinic_timezone(db, clinic_id))


@router.put("/{doctor_id}/availability", response_model=DoctorAvailabilityResponse)
def replace_doctor_availability(
    doctor_id: int,
    data: AvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Reemplaza el horario semanal completo del doctor.

    Administración y recepción editan el de cualquier doctor; un doctor, solo
    el suyo (docs/PERMISSIONS.md)."""
    doctor = _get_clinic_doctor(db, doctor_id, clinic_id)

    if current_user.role == Role.DOCTOR.value and doctor.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes editar tu propio horario.",
        )

    doctor.availability = [
        DoctorAvailabilityBlock(clinic_id=clinic_id, **block.model_dump()) for block in data.blocks
    ]
    db.commit()

    audit_logger.info(
        "doctor.availability_updated doctor_id=%s user_id=%s clinic_id=%s blocks=%s",
        doctor.id, current_user.id, clinic_id, len(data.blocks),
    )
    db.expire_all()
    doctor = _get_clinic_doctor(db, doctor_id, clinic_id)
    return _availability(doctor, _clinic_timezone(db, clinic_id))


def _get_clinic_doctor(db: Session, doctor_id: int, clinic_id: int) -> Doctor:
    doctor = _clinic_doctors(db, clinic_id).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor no encontrado."
        )
    return doctor


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


@router.patch(
    "/{doctor_id}",
    response_model=DoctorResponse,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
def update_doctor(
    doctor_id: int,
    changes: DoctorUpdate,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):
    """Edita especialidad, colegiado o teléfono. Solo cambian los campos
    enviados; enviar null o "" borra ese dato."""

    doctor = _clinic_doctors(db, clinic_id).filter(Doctor.id == doctor_id).first()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor no encontrado."
        )

    for field, value in changes.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    db.commit()

    return _clinic_doctors(db, clinic_id).filter(Doctor.id == doctor_id).one()
