"""Datos y ayudas compartidas por las pruebas de citas (ODON-134 y ODON-146)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.security import hash_password
from app.models import Appointment, Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

ROLES = ("admin", "doctor", "receptionist")
GT = timezone(timedelta(hours=-6))


def tomorrow_at(hour: int, minute: int = 0) -> datetime:
    """Una hora fija de pasado mañana en Guatemala: siempre en el futuro."""
    day = (datetime.now(GT) + timedelta(days=2)).date()
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=GT)


NINE = tomorrow_at(9)


def iso(value: datetime) -> str:
    return value.isoformat()


@pytest.fixture
def agenda(db, client):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Citas", "doc@citas-clinica.com")
    other_clinic, _, foreign_doctor = create_clinic_with_doctor(db, "Clinica Lejana Citas", "doc@lejana-citas.com")

    second_user = User(name="Dra. Segunda", email="segunda@citas-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id)
    retired_user = User(name="Dr. Retirado", email="retirado@citas-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id, is_active=False)
    db.add_all([second_user, retired_user])
    for role in ("admin", "receptionist"):
        db.add(User(name=role, email=f"{role}@citas-clinica.com", hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic.id))
    db.flush()
    second = Doctor(user_id=second_user.id, clinic_id=clinic.id)
    retired = Doctor(user_id=retired_user.id, clinic_id=clinic.id)
    patients = [Patient(first_name=f"Paciente{i}", last_name="Agenda", phone="5555-0000", clinic_id=clinic.id) for i in range(6)]
    archived = Patient(first_name="Archivada", last_name="Agenda", clinic_id=clinic.id, archived_at=datetime.now(timezone.utc))
    foreign_patient = Patient(first_name="Ajena", last_name="Agenda", clinic_id=other_clinic.id)
    db.add_all([second, retired, *patients, archived, foreign_patient])
    db.commit()

    return {
        "clinic": clinic.id, "doctor": doctor.id, "second": second.id, "retired": retired.id,
        "foreign_doctor": foreign_doctor.id, "patients": [p.id for p in patients],
        "patient": patients[0].id, "archived": archived.id, "foreign_patient": foreign_patient.id,
        "doctor_user": doctor_user.id,
        "headers": {
            "admin": auth_headers(client, "admin@citas-clinica.com"),
            "doctor": auth_headers(client, "doc@citas-clinica.com"),
            "receptionist": auth_headers(client, "receptionist@citas-clinica.com"),
            "other": auth_headers(client, "doc@lejana-citas.com"),
        },
    }


def payload(agenda, starts_at=NINE, **overrides):
    data = {"patient_id": agenda["patient"], "doctor_id": agenda["doctor"], "starts_at": iso(starts_at), "duration_minutes": 30}
    data.update(overrides)
    return data


def create(client, agenda, role="receptionist", **kwargs):
    return client.post("/appointments/", json=payload(agenda, **kwargs), headers=agenda["headers"][role])


def created_id(client, agenda, **kwargs) -> int:
    response = create(client, agenda, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def set_status(db, appointment_id, status):
    appointment = db.get(Appointment, appointment_id)
    appointment.status = status
    db.commit()


def listing(client, agenda, role="receptionist", **params):
    return client.get("/appointments/", params=params, headers=agenda["headers"][role])


def day_range():
    start = NINE.replace(hour=0)
    return {"start": iso(start), "end": iso(start + timedelta(days=1))}
