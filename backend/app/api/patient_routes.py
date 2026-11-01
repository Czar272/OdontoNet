from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, joinedload

from app.auth.dependencies import get_current_clinic_id
from app.auth.permissions import ALL_ROLES, require_roles
from app.database.dependencies import get_db
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.patient_schema import PatientCreate, PatientResponse

# Administración, doctores y recepción gestionan pacientes (docs/PERMISSIONS.md).
router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
    dependencies=[Depends(require_roles(*ALL_ROLES))],
)


def _clinic_patients(db: Session, clinic_id: int) -> Query:
    """Pacientes de la clínica indicada, con su doctor y usuario cargados."""
    return (
        db.query(Patient)
        .options(joinedload(Patient.doctor).joinedload(Doctor.user))
        .filter(Patient.clinic_id == clinic_id)
    )


def _ensure_doctor_in_clinic(db: Session, doctor_id: int, clinic_id: int) -> None:
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.user))
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic_id)
        .first()
    )

    if not doctor:
        # Mismo mensaje si no existe o si es de otra clínica: no se revela nada.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El doctor seleccionado no pertenece a la clínica.",
        )

    if doctor.user.is_active is False:
        # Los pacientes ya asignados lo conservan (ODON-94); no se asignan nuevos.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El doctor seleccionado está inactivo.",
        )


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient: PatientCreate,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    if patient.doctor_id is not None:
        _ensure_doctor_in_clinic(db, patient.doctor_id, clinic_id)

    new_patient = Patient(**patient.dict(), clinic_id=clinic_id)

    db.add(new_patient)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_patients_clinic_email" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un paciente con ese correo en la clínica.",
            )
        # Otra restricción (p. ej. fk_patients_doctor_clinic si el doctor cambió
        # entre la validación y el guardado): mismo mensaje que la validación.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El doctor seleccionado no pertenece a la clínica.",
        )

    return _clinic_patients(db, clinic_id).filter(Patient.id == new_patient.id).one()


@router.get("/", response_model=list[PatientResponse])
def get_patients(
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    return _clinic_patients(db, clinic_id).order_by(Patient.id).all()


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    clinic_id: int = Depends(get_current_clinic_id),
):

    patient = _clinic_patients(db, clinic_id).filter(Patient.id == patient_id).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado."
        )

    return patient
