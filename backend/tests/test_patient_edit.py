"""Detalle y edición de pacientes, reasignación de doctor (ODON-114 / ODON-118)."""
import logging

import pytest

from app.auth.security import hash_password
from app.models import Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.patients]

ROLES = ("admin", "doctor", "receptionist")


@pytest.fixture
def setup(db, client):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Edicion", "doc@edicion-clinica.com")
    other_clinic, _, foreign_doctor = create_clinic_with_doctor(db, "Clinica Lejana", "doc@lejana-clinica.com")

    second_user = User(name="Dra. Segunda", email="segunda@edicion-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id)
    retired_user = User(name="Dr. Retirado", email="retirado@edicion-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id, is_active=False)
    db.add_all([second_user, retired_user])
    db.flush()
    second = Doctor(user_id=second_user.id, clinic_id=clinic.id)
    retired = Doctor(user_id=retired_user.id, clinic_id=clinic.id)
    db.add_all([second, retired])
    for role in ("admin", "receptionist"):
        db.add(User(name=role, email=f"{role}@edicion-clinica.com", hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic.id))
    db.flush()

    patient = Patient(first_name="Eva", last_name="Luna", phone="5555-0000", email="eva@luna.com", clinic_id=clinic.id, doctor_id=doctor.id)
    with_retired = Patient(first_name="Iván", last_name="Mora", clinic_id=clinic.id, doctor_id=retired.id)
    other = Patient(first_name="Ajeno", last_name="X", email="ajeno@x.com", clinic_id=other_clinic.id)
    db.add_all([patient, with_retired, other])
    db.commit()

    headers = {
        "admin": auth_headers(client, "admin@edicion-clinica.com"),
        "doctor": auth_headers(client, "doc@edicion-clinica.com"),
        "receptionist": auth_headers(client, "receptionist@edicion-clinica.com"),
    }
    return {
        "patient": patient.id, "with_retired": with_retired.id, "other": other.id,
        "doctor": doctor.id, "second": second.id, "retired": retired.id, "foreign": foreign_doctor.id,
        "headers": headers,
    }


def patch(client, setup, payload, role="receptionist", patient="patient"):
    return client.patch(f"/patients/{setup[patient]}", json=payload, headers=setup["headers"][role])


# --- Detalle (ODON-115 / ODON-117) ---------------------------------------------------

@pytest.mark.parametrize("role", ROLES)
def test_detail_for_every_role(client, setup, role):
    response = client.get(f"/patients/{setup['patient']}", headers=setup["headers"][role])

    assert response.status_code == 200
    assert response.json()["first_name"] == "Eva"
    assert response.json()["doctor"]["user"]["name"] == "Dr. Clinica Edicion"


@pytest.mark.isolation
def test_detail_of_other_clinic_is_not_found(client, setup):
    response = client.get(f"/patients/{setup['other']}", headers=setup["headers"]["admin"])

    assert response.status_code == 404
    assert response.json()["detail"] == "Paciente no encontrado."


def test_detail_with_invalid_id_is_422(client, setup):
    assert client.get("/patients/abc", headers=setup["headers"]["admin"]).status_code == 422


# --- Edición (ODON-119) --------------------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_edit(client, setup, role):
    response = patch(client, setup, {"phone": "5555-1234"}, role=role)

    assert response.status_code == 200
    assert response.json()["phone"] == "5555-1234"


def test_partial_edit_persists(client, setup):
    patch(client, setup, {"first_name": " Eva María ", "address": "Zona 10"})

    body = client.get(f"/patients/{setup['patient']}", headers=setup["headers"]["admin"]).json()
    assert (body["first_name"], body["last_name"], body["address"], body["phone"]) == ("Eva María", "Luna", "Zona 10", "5555-0000")


def test_optional_fields_can_be_cleared(client, setup):
    body = patch(client, setup, {"phone": "", "email": None}).json()

    assert body["phone"] is None and body["email"] is None


@pytest.mark.parametrize("payload", [{"first_name": None}, {"last_name": ""}, {"email": "no-es-correo"}, {"birth_date": "2999-01-01"}])
def test_rejects_invalid_data(client, setup, payload):
    assert patch(client, setup, payload).status_code == 422


def test_duplicate_email_in_clinic_conflicts(client, setup, db):
    db.add(Patient(first_name="Otra", last_name="Paciente", email="otra@correo.com", clinic_id=db.get(Patient, setup["patient"]).clinic_id))
    db.commit()

    response = patch(client, setup, {"email": "otra@correo.com"})

    assert response.status_code == 409


@pytest.mark.isolation
def test_email_used_in_other_clinic_is_allowed(client, setup):
    assert patch(client, setup, {"email": "ajeno@x.com"}).status_code == 200


@pytest.mark.isolation
def test_cannot_edit_patient_of_other_clinic(client, setup):
    assert patch(client, setup, {"first_name": "Hack"}, patient="other").status_code == 404


@pytest.mark.isolation
def test_clinic_id_is_ignored(client, setup):
    body = patch(client, setup, {"clinic_id": 999, "phone": "1"}).json()

    assert body["clinic_id"] != 999


# --- Reasignación de doctor -------------------------------------------------------------

@pytest.mark.doctors
def test_reassign_to_active_doctor_of_same_clinic(client, setup):
    body = patch(client, setup, {"doctor_id": setup["second"]}).json()

    assert body["doctor"]["user"]["name"] == "Dra. Segunda"


@pytest.mark.doctors
def test_unassign_doctor(client, setup):
    body = patch(client, setup, {"doctor_id": None}).json()

    assert body["doctor_id"] is None and body["doctor"] is None


@pytest.mark.doctors
@pytest.mark.isolation
def test_cannot_assign_doctor_of_other_clinic(client, setup):
    response = patch(client, setup, {"doctor_id": setup["foreign"]})

    assert response.status_code == 422
    assert response.json()["detail"] == "El doctor seleccionado no pertenece a la clínica."


@pytest.mark.doctors
def test_cannot_assign_inactive_doctor(client, setup):
    response = patch(client, setup, {"doctor_id": setup["retired"]})

    assert response.status_code == 422
    assert response.json()["detail"] == "El doctor seleccionado está inactivo."


@pytest.mark.doctors
def test_patient_of_inactive_doctor_can_still_be_edited(client, setup):
    response = patch(client, setup, {"phone": "5555-7777", "doctor_id": setup["retired"]}, patient="with_retired")

    assert response.status_code == 200
    assert response.json()["doctor"]["user"]["name"] == "Dr. Retirado"


# --- Auditoría (ODON-121) ------------------------------------------------------------------

def test_relevant_changes_are_audited_without_personal_data(client, setup, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        patch(client, setup, {"phone": "5555-9999", "doctor_id": setup["second"]})

    messages = [record.getMessage() for record in caplog.records if record.name == "odontonet.audit"]
    assert any("patient.updated" in m and "fields=doctor_id,phone" in m for m in messages)
    assert any("patient.doctor_changed" in m and f"to={setup['second']}" in m for m in messages)
    assert not any("5555-9999" in m for m in messages)


def test_no_audit_when_nothing_changes(client, setup, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        patch(client, setup, {"phone": "5555-0000"})

    assert not [r for r in caplog.records if r.name == "odontonet.audit"]
