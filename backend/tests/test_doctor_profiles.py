"""Perfil clínico de doctores: alta, edición y validación de rol (ODON-90)."""
import pytest

from app.auth.security import hash_password
from app.models import Clinic, Doctor, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.doctors]

ROLES = ("admin", "doctor", "receptionist")


@pytest.fixture
def staff(db, client):
    clinic = Clinic(name="Clinica Perfiles")
    other = Clinic(name="Clinica Externa")
    db.add_all([clinic, other])
    db.flush()

    def add_user(clinic_id, email, role):
        user = User(name=f"Usuario {email}", email=email, hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic_id)
        db.add(user)
        db.flush()
        return user

    users = {role: add_user(clinic.id, f"{role}@perfiles-clinica.com", role) for role in ROLES}
    new_doctor = add_user(clinic.id, "nuevo.doctor@perfiles-clinica.com", "doctor")
    profile = Doctor(user_id=users["doctor"].id, clinic_id=clinic.id, specialization="Periodoncia", license_number="COL-1", phone="5555-0001")
    outsider_user = add_user(other.id, "externo@externa-clinica.com", "doctor")
    db.add(profile)
    db.flush()
    outsider = Doctor(user_id=outsider_user.id, clinic_id=other.id)
    db.add(outsider)
    db.commit()

    return {
        "ids": {**{role: user.id for role, user in users.items()}, "new_doctor": new_doctor.id, "profile": profile.id, "outsider": outsider.id},
        "headers": {role: auth_headers(client, f"{role}@perfiles-clinica.com") for role in ROLES},
    }


def admin(staff):
    return staff["headers"]["admin"]


# --- Alta: validación de rol ---------------------------------------------------

def test_create_profile_with_license_and_specialization(client, staff):
    payload = {"user_id": staff["ids"]["new_doctor"], "specialization": " Ortodoncia ", "license_number": "COL-2", "phone": ""}

    response = client.post("/doctors/", json=payload, headers=admin(staff))

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["specialization"], body["license_number"], body["phone"]) == ("Ortodoncia", "COL-2", None)


@pytest.mark.parametrize("role", ["admin", "receptionist"])
def test_profile_requires_doctor_role(client, staff, role):
    response = client.post("/doctors/", json={"user_id": staff["ids"][role]}, headers=admin(staff))

    assert response.status_code == 422
    assert response.json()["detail"] == "El usuario no tiene rol de doctor."


def test_profile_is_unique_per_user(client, staff):
    response = client.post("/doctors/", json={"user_id": staff["ids"]["doctor"]}, headers=admin(staff))

    assert response.status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [("specialization", "x" * 101), ("license_number", "x" * 51), ("phone", "x" * 31)],
)
def test_create_rejects_too_long_fields(client, staff, field, value):
    payload = {"user_id": staff["ids"]["new_doctor"], field: value}

    response = client.post("/doctors/", json=payload, headers=admin(staff))

    assert response.status_code == 422
    assert field in {error["field"] for error in response.json()["errors"]}


# --- Edición ----------------------------------------------------------------------

def test_update_changes_only_sent_fields(client, staff):
    response = client.patch(f"/doctors/{staff['ids']['profile']}", json={"specialization": "Endodoncia"}, headers=admin(staff))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["specialization"] == "Endodoncia"
    assert body["license_number"] == "COL-1"
    assert body["phone"] == "5555-0001"
    assert body["user"]["name"] == "Usuario doctor@perfiles-clinica.com"


def test_update_can_clear_a_field(client, staff):
    response = client.patch(f"/doctors/{staff['ids']['profile']}", json={"phone": ""}, headers=admin(staff))

    assert response.json()["phone"] is None


def test_update_ignores_user_and_clinic(client, staff):
    response = client.patch(
        f"/doctors/{staff['ids']['profile']}",
        json={"user_id": staff["ids"]["new_doctor"], "clinic_id": 999, "license_number": "COL-9"},
        headers=admin(staff),
    )

    body = response.json()
    assert body["user_id"] == staff["ids"]["doctor"]
    assert body["clinic_id"] != 999
    assert body["license_number"] == "COL-9"


def test_update_rejects_invalid_data(client, staff):
    response = client.patch(f"/doctors/{staff['ids']['profile']}", json={"license_number": "x" * 51}, headers=admin(staff))

    assert response.status_code == 422


@pytest.mark.isolation
def test_update_doctor_of_other_clinic_is_not_found(client, staff):
    response = client.patch(f"/doctors/{staff['ids']['outsider']}", json={"specialization": "Hack"}, headers=admin(staff))

    assert response.status_code == 404


@pytest.mark.rbac
@pytest.mark.parametrize("role,expected", [("admin", 200), ("doctor", 403), ("receptionist", 403)])
def test_only_admin_edits_profiles(client, staff, role, expected):
    response = client.patch(f"/doctors/{staff['ids']['profile']}", json={"phone": "5555-9999"}, headers=staff["headers"][role])

    assert response.status_code == expected


# --- Estado activo -------------------------------------------------------------------

@pytest.mark.users
def test_active_state_comes_from_user(client, staff):
    client.post(f"/users/{staff['ids']['doctor']}/deactivate", headers=admin(staff))

    body = client.get(f"/doctors/{staff['ids']['profile']}", headers=admin(staff)).json()

    assert body["user"]["is_active"] is False
