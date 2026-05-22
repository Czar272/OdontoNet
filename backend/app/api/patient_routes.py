from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from app.database.dependencies import get_db
from app.models.patient import Patient
from app.schemas.patient_schema import PatientCreate, PatientResponse
from app.models.doctor import Doctor

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("/", response_model=PatientResponse)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):

    new_patient = Patient(**patient.dict())

    db.add(new_patient)

    db.commit()

    db.refresh(new_patient)

    return new_patient


@router.get("/", response_model=list[PatientResponse])
def get_patients(db: Session = Depends(get_db)):

    patients = (
        db.query(Patient)
        .options(joinedload(Patient.doctor).joinedload(Doctor.user))
        .all()
    )

    return patients
