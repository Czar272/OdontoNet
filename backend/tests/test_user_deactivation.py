"""Desactivación segura de personal (ODON-94 / ODON-97)."""
import pytest

from app.auth.security import hash_password
from app.models import Clinic, Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.users]

ROLES = ("admin", "doctor", "receptionist")


@pytest.fixture
def staff(db, client):
    """Clínica con un usuario por rol; el doctor tiene un paciente asignado.
    Otra clínica con su propio usuario."""
    clinic = Clinic(name="Clinica Activa")
    other = Clinic(name="Clinica Ajena")
    db.add_all([clinic, other])
    db.flush()

    users = {}
    for role in ROLES:
        users[role] = User(
            name=f"Usuario {role}",
            email=f"{role}@activa-clinica.com",
            hashed_password=hash_password(PASSWORD),
            role=role,
            clinic_id=clinic.id,
        )
    outsider = User(
        name="Ajeno",
        email="ajeno@ajena-clinica.com",
        hashed_password=hash_password(PASSWORD),
        role="doctor",
        clinic_id=other.id,
    )
    db.add_all([*users.values(), outsider])
    db.flush()

    doctor = Doctor(user_id=users["doctor"].id, clinic_id=clinic.id)
    db.add(doctor)
    db.flush()
    patient = Patient(first_name="Lucía", last_name="Paz", doctor_id=doctor.id, clinic_id=clinic.id)
    db.add(patient)
    db.commit()

    return {
        "ids": {**{role: user.id for role, user in users.items()}, "outsider": outsider.id, "patient": patient.id},
        "headers": {role: auth_headers(client, f"{role}@activa-clinica.com") for role in ROLES},
    }


def deactivate(client, staff, user_id, role="admin"):
    return client.post(f"/users/{user_id}/deactivate", headers=staff["headers"][role])


def activate(client, staff, user_id, role="admin"):
    return client.post(f"/users/{user_id}/activate", headers=staff["headers"][role])


# --- Autorización -----------------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("action", ["deactivate", "activate"])
@pytest.mark.parametrize("role,expected", [("admin", 200), ("doctor", 403), ("receptionist", 403)])
def test_only_admin_changes_active_state(client, staff, action, role, expected):
    target = staff["ids"]["receptionist"] if role != "receptionist" else staff["ids"]["doctor"]

    response = client.post(f"/users/{target}/{action}", headers=staff["headers"][role])

    assert response.status_code == expected


@pytest.mark.auth
def test_requires_authentication(client, staff):
    assert client.post(f"/users/{staff['ids']['doctor']}/deactivate").status_code == 401


@pytest.mark.isolation
@pytest.mark.parametrize("action", ["deactivate", "activate"])
def test_user_from_other_clinic_is_not_found(client, staff, action):
    response = client.post(f"/users/{staff['ids']['outsider']}/{action}", headers=staff["headers"]["admin"])

    assert response.status_code == 404


def test_admin_cannot_deactivate_self(client, staff):
    response = deactivate(client, staff, staff["ids"]["admin"])

    assert response.status_code == 409
    assert response.json()["detail"] == "No puedes desactivar tu propia cuenta."


# --- Revocación de acceso ---------------------------------------------------

def test_deactivate_marks_user_inactive(client, staff):
    response = deactivate(client, staff, staff["ids"]["receptionist"])

    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.auth
def test_deactivated_user_cannot_log_in(client, staff):
    deactivate(client, staff, staff["ids"]["receptionist"])

    response = client.post("/auth/login", json={"email": "receptionist@activa-clinica.com", "password": PASSWORD})

    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas."


@pytest.mark.auth
@pytest.mark.parametrize("path", ["/auth/me", "/patients/", "/doctors/"])
def test_existing_token_stops_working_immediately(client, staff, path):
    doctor_headers = staff["headers"]["doctor"]
    assert client.get(path, headers=doctor_headers).status_code == 200

    deactivate(client, staff, staff["ids"]["doctor"])

    response = client.get(path, headers=doctor_headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario no encontrado o inactivo."


@pytest.mark.auth
def test_deactivated_admin_loses_admin_actions(client, staff, db):
    second_admin = User(
        name="Admin 2",
        email="admin2@activa-clinica.com",
        hashed_password=hash_password(PASSWORD),
        role="admin",
        clinic_id=db.get(User, staff["ids"]["admin"]).clinic_id,
    )
    db.add(second_admin)
    db.commit()
    second_headers = auth_headers(client, "admin2@activa-clinica.com")

    deactivate(client, staff, second_admin.id)

    assert client.get("/users/", headers=second_headers).status_code == 401


@pytest.mark.auth
def test_reactivated_user_can_log_in_again(client, staff):
    deactivate(client, staff, staff["ids"]["receptionist"])

    response = activate(client, staff, staff["ids"]["receptionist"])

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert client.post("/auth/login", json={"email": "receptionist@activa-clinica.com", "password": PASSWORD}).status_code == 200


def test_operations_are_idempotent(client, staff):
    target = staff["ids"]["receptionist"]

    assert deactivate(client, staff, target).json()["is_active"] is False
    assert deactivate(client, staff, target).json()["is_active"] is False
    assert activate(client, staff, target).json()["is_active"] is True
    assert activate(client, staff, target).json()["is_active"] is True


# --- Historial ----------------------------------------------------------------

def test_deactivated_user_stays_listed(client, staff):
    deactivate(client, staff, staff["ids"]["receptionist"])

    users = client.get("/users/", headers=staff["headers"]["admin"]).json()

    receptionist = next(user for user in users if user["id"] == staff["ids"]["receptionist"])
    assert receptionist["is_active"] is False


@pytest.mark.patients
@pytest.mark.doctors
def test_history_of_deactivated_doctor_is_preserved(client, staff, db):
    deactivate(client, staff, staff["ids"]["doctor"])

    patients = client.get("/patients/", headers=staff["headers"]["admin"]).json()["items"]

    patient = next(p for p in patients if p["id"] == staff["ids"]["patient"])
    assert patient["doctor"]["user"]["name"] == "Usuario doctor"
    assert db.query(Doctor).filter(Doctor.user_id == staff["ids"]["doctor"]).count() == 1
    assert db.get(User, staff["ids"]["doctor"]) is not None


def test_patch_cannot_change_active_state(client, staff):
    target = staff["ids"]["receptionist"]

    response = client.patch(f"/users/{target}", json={"is_active": False, "name": "Sigue activa"}, headers=staff["headers"]["admin"])

    assert response.status_code == 200
    assert response.json()["is_active"] is True
