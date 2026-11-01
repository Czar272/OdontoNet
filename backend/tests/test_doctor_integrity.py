"""Relación uno a uno User–Doctor e integridad de claves foráneas (ODON-78 / ODON-81)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.security import hash_password
from app.models import Clinic, Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.doctors]


@pytest.fixture
def clinics(db):
    """Dos clínicas; en la primera, un usuario con perfil de doctor y otro sin él."""
    norte = Clinic(name="Clinica Integridad")
    sur = Clinic(name="Clinica Otra")
    db.add_all([norte, sur])
    db.flush()

    def add_user(clinic, email, role="doctor"):
        user = User(name=f"Usuario {email}", email=email, hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic.id)
        db.add(user)
        db.flush()
        return user

    with_profile = add_user(norte, "con.perfil@integridad-clinica.com")
    without_profile = add_user(norte, "sin.perfil@integridad-clinica.com")
    admin = add_user(norte, "admin@integridad-clinica.com", role="admin")
    doctor = Doctor(user_id=with_profile.id, clinic_id=norte.id, specialization="Periodoncia")
    db.add(doctor)
    db.commit()

    return {
        "norte": norte.id,
        "sur": sur.id,
        "with_profile": with_profile.id,
        "without_profile": without_profile.id,
        "admin": admin.id,
        "doctor": doctor.id,
    }


# --- Base de datos ----------------------------------------------------------

def test_database_rejects_second_profile_for_same_user(db, clinics):
    db.add(Doctor(user_id=clinics["with_profile"], clinic_id=clinics["norte"]))

    with pytest.raises(IntegrityError, match="uq_doctors_user_id"):
        db.commit()
    db.rollback()


@pytest.mark.isolation
def test_database_rejects_profile_in_other_clinic_than_user(db, clinics):
    db.add(Doctor(user_id=clinics["without_profile"], clinic_id=clinics["sur"]))

    with pytest.raises(IntegrityError, match="fk_doctors_user_clinic"):
        db.commit()
    db.rollback()


def test_database_rejects_profile_for_unknown_user(db, clinics):
    db.add(Doctor(user_id=999_999, clinic_id=clinics["norte"]))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_with_profile_cannot_be_deleted(db, clinics):
    # Retirar acceso es desactivar (ODON-94); borrar dejaría pacientes sin historial.
    db.delete(db.get(User, clinics["with_profile"]))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.patients
def test_doctor_with_patients_cannot_be_deleted(db, clinics):
    db.add(Patient(first_name="Eva", last_name="Luna", doctor_id=clinics["doctor"], clinic_id=clinics["norte"]))
    db.commit()

    db.delete(db.get(Doctor, clinics["doctor"]))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- Relaciones ORM -----------------------------------------------------------

def test_orm_relationships_are_one_to_one(db, clinics):
    user = db.get(User, clinics["with_profile"])
    doctor = db.get(Doctor, clinics["doctor"])

    assert user.doctor_profile is doctor
    assert doctor.user is user
    assert doctor.clinic.id == user.clinic.id == clinics["norte"]
    assert db.get(User, clinics["without_profile"]).doctor_profile is None


# --- API ------------------------------------------------------------------------

def test_api_returns_real_names_nested(client, clinics):
    headers = auth_headers(client, "admin@integridad-clinica.com")

    body = client.get(f"/doctors/{clinics['doctor']}", headers=headers).json()

    assert body["user"]["name"] == "Usuario con.perfil@integridad-clinica.com"
    assert body["user"]["id"] == body["user_id"] == clinics["with_profile"]
    assert body["clinic_id"] == body["user"]["clinic_id"]
    assert set(body["user"]) == {"id", "name", "email", "role", "clinic_id", "is_active"}


@pytest.mark.patients
def test_patient_response_nests_doctor_and_user(client, clinics):
    headers = auth_headers(client, "admin@integridad-clinica.com")

    patient = client.post(
        "/patients/",
        json={"first_name": "Eva", "last_name": "Luna", "doctor_id": clinics["doctor"]},
        headers=headers,
    ).json()

    assert patient["doctor"]["id"] == clinics["doctor"]
    assert patient["doctor"]["user"]["name"] == "Usuario con.perfil@integridad-clinica.com"
    assert "hashed_password" not in patient["doctor"]["user"]


def test_api_second_profile_conflicts(client, clinics):
    headers = auth_headers(client, "admin@integridad-clinica.com")

    response = client.post("/doctors/", json={"user_id": clinics["with_profile"]}, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "El usuario ya tiene un perfil de doctor."


def test_api_creates_profile_for_user_without_one(client, clinics):
    headers = auth_headers(client, "admin@integridad-clinica.com")

    response = client.post("/doctors/", json={"user_id": clinics["without_profile"], "specialization": "Ortodoncia"}, headers=headers)

    assert response.status_code == 201
    assert response.json()["user"]["name"] == "Usuario sin.perfil@integridad-clinica.com"
    assert response.json()["clinic_id"] == clinics["norte"]
