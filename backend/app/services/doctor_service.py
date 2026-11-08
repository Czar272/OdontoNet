"""Reglas compartidas sobre doctores de la clínica (pacientes y citas)."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.doctor import Doctor


def ensure_assignable_doctor(db: Session, doctor_id: int, clinic_id: int) -> Doctor:
    """Doctor activo de la clínica, o 422 con un mensaje en español.

    Se usa al asignar un doctor a un paciente (ODON-82) y al agendar o
    reprogramar una cita (ODON-134). Un doctor de otra clínica recibe el mismo
    mensaje que uno inexistente: no se revela nada de otras clínicas."""
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.user))
        .filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic_id)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El doctor seleccionado no pertenece a la clínica.",
        )

    if doctor.user.is_active is False:
        # Lo ya asignado se conserva (ODON-94); solo se bloquea lo nuevo.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El doctor seleccionado está inactivo.",
        )

    return doctor
