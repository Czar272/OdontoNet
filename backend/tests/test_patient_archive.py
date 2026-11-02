"""Archivar y reactivar pacientes, y conservación del historial (ODON-122 / ODON-125)."""
import logging

import pytest

from app.auth.security import hash_password
from app.models import Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.patients]

ROLES = ("admin", "doctor", "receptionist")


@pytest.fixture
def setup(db, client):
    clinic, _, doctor = create_clinic_with_doctor(db, "Clinica Archivo", "doc@archivo-clinica.com")
    other_clinic, _, _ = create_clinic_with_doctor(db, "Clinica Vecina", "doc@vecina-clinica.com")

    retired_user = User(name="Dr. Retirado", email="retirado@archivo-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id, is_active=False)
    db.add(retired_user)
    for role in ("admin", "receptionist"):
        db.add(User(name=role, email=f"{role}@archivo-clinica.com", hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic.id))
    db.flush()
    retired = Doctor(user_id=retired_user.id, clinic_id=clinic.id)
    db.add(retired)
    db.flush()

    patient = Patient(first_name="Eva", last_name="Luna", phone="5555-0000", email="eva@luna.com", address="Zona 1", clinic_id=clinic.id, doctor_id=doctor.id)
    with_retired = Patient(first_name="Iván", last_name="Mora", clinic_id=clinic.id, doctor_id=retired.id)
    other = Patient(first_name="Ajeno", last_name="X", email="ajeno@x.com", clinic_id=other_clinic.id)
    db.add_all([patient, with_retired, other])
    db.commit()

    headers = {
        "admin": auth_headers(client, "admin@archivo-clinica.com"),
        "doctor": auth_headers(client, "doc@archivo-clinica.com"),
        "receptionist": auth_headers(client, "receptionist@archivo-clinica.com"),
        "other": auth_headers(client, "doc@vecina-clinica.com"),
    }
    return {
        "patient": patient.id, "with_retired": with_retired.id, "other": other.id,
        "doctor": doctor.id, "retired": retired.id, "headers": headers,
    }


def archive(client, setup, role="receptionist", patient="patient"):
    return client.post(f"/patients/{setup[patient]}/archive", headers=setup["headers"][role])


def reactivate(client, setup, role="receptionist", patient="patient"):
    return client.post(f"/patients/{setup[patient]}/reactivate", headers=setup["headers"][role])


def listed_ids(client, setup, role="receptionist", **params):
    response = client.get("/patients/", params=params, headers=setup["headers"][role])
    assert response.status_code == 200, response.text
    return {p["id"] for p in response.json()}


# --- Archivar y reactivar (ODON-124) -------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_archive_and_reactivate(client, setup, role):
    archived = archive(client, setup, role)
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] is not None

    reactivated = reactivate(client, setup, role)
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["archived_at"] is None


def test_new_and_existing_patients_are_active(client, setup):
    detail = client.get(f"/patients/{setup['patient']}", headers=setup["headers"]["admin"]).json()
    created = client.post("/patients/", json={"first_name": "Nuevo", "last_name": "Paciente"}, headers=setup["headers"]["admin"]).json()

    assert detail["archived_at"] is None
    assert created["archived_at"] is None


def test_list_shows_only_active_by_default(client, setup):
    archive(client, setup)

    assert listed_ids(client, setup) == {setup["with_retired"]}
    assert listed_ids(client, setup, archived="false") == {setup["with_retired"]}
    assert listed_ids(client, setup, archived="true") == {setup["patient"]}


def test_reactivated_patient_returns_to_active_list(client, setup):
    archive(client, setup)
    reactivate(client, setup)

    assert listed_ids(client, setup) == {setup["patient"], setup["with_retired"]}
    assert listed_ids(client, setup, archived="true") == set()


def test_invalid_archived_filter_is_422(client, setup):
    response = client.get("/patients/", params={"archived": "quizas"}, headers=setup["headers"]["admin"])

    assert response.status_code == 422


def test_archive_is_idempotent(client, setup, db):
    first = archive(client, setup).json()["archived_at"]
    second = archive(client, setup)

    assert second.status_code == 200
    assert second.json()["archived_at"] == first


def test_reactivate_active_patient_is_noop(client, setup):
    response = reactivate(client, setup)

    assert response.status_code == 200
    assert response.json()["archived_at"] is None


def test_unknown_patient_is_404(client, setup):
    for action in ("archive", "reactivate"):
        response = client.post(f"/patients/999999/{action}", headers=setup["headers"]["admin"])
        assert response.status_code == 404
        assert response.json()["detail"] == "Paciente no encontrado."


def test_invalid_id_is_422(client, setup):
    assert client.post("/patients/abc/archive", headers=setup["headers"]["admin"]).status_code == 422


@pytest.mark.auth
def test_archive_requires_session(client, setup):
    assert client.post(f"/patients/{setup['patient']}/archive").status_code == 401
    assert client.post(f"/patients/{setup['patient']}/reactivate").status_code == 401


# --- Aislamiento ---------------------------------------------------------------------

@pytest.mark.isolation
def test_cannot_archive_patient_of_other_clinic(client, setup, db):
    response = archive(client, setup, "admin", patient="other")

    assert response.status_code == 404
    assert response.json()["detail"] == "Paciente no encontrado."
    assert db.get(Patient, setup["other"]).archived_at is None


@pytest.mark.isolation
def test_cannot_reactivate_patient_of_other_clinic(client, setup, db):
    client.post(f"/patients/{setup['other']}/archive", headers=setup["headers"]["other"])

    response = reactivate(client, setup, "admin", patient="other")

    assert response.status_code == 404
    db.expire_all()
    assert db.get(Patient, setup["other"]).archived_at is not None


@pytest.mark.isolation
def test_archived_list_does_not_leak_other_clinic(client, setup):
    client.post(f"/patients/{setup['other']}/archive", headers=setup["headers"]["other"])

    assert listed_ids(client, setup, "admin", archived="true") == set()
    assert listed_ids(client, setup, "other", archived="true") == {setup["other"]}


# --- Historial conservado (ODON-125) -------------------------------------------------

def test_archiving_preserves_all_patient_data(client, setup):
    before = client.get(f"/patients/{setup['patient']}", headers=setup["headers"]["admin"]).json()

    archive(client, setup)
    after = client.get(f"/patients/{setup['patient']}", headers=setup["headers"]["admin"])

    assert after.status_code == 200
    body = after.json()
    assert body["archived_at"] is not None
    assert {k: v for k, v in body.items() if k != "archived_at"} == {
        k: v for k, v in before.items() if k != "archived_at"
    }


def test_round_trip_keeps_data_and_assignment(client, setup):
    before = client.get(f"/patients/{setup['with_retired']}", headers=setup["headers"]["admin"]).json()

    archive(client, setup, patient="with_retired")
    after = reactivate(client, setup, patient="with_retired").json()

    # El doctor inactivo sigue asignado tras reactivar: no se revalida la asignación.
    assert after == before
    assert after["doctor"]["id"] == setup["retired"]


def test_archived_patient_cannot_be_edited(client, setup, db):
    archive(client, setup)

    response = client.patch(f"/patients/{setup['patient']}", json={"phone": "1111-1111"}, headers=setup["headers"]["admin"])

    assert response.status_code == 409
    assert response.json()["detail"] == "El paciente está archivado. Reactívalo para editar sus datos."
    assert db.get(Patient, setup["patient"]).phone == "5555-0000"


def test_reactivated_patient_can_be_edited(client, setup):
    archive(client, setup)
    reactivate(client, setup)

    response = client.patch(f"/patients/{setup['patient']}", json={"phone": "1111-1111"}, headers=setup["headers"]["admin"])

    assert response.status_code == 200
    assert response.json()["phone"] == "1111-1111"


def test_archived_patient_keeps_email_reserved(client, setup):
    archive(client, setup)

    response = client.post("/patients/", json={"first_name": "Otra", "last_name": "Eva", "email": "eva@luna.com"}, headers=setup["headers"]["admin"])

    assert response.status_code == 409


def test_archive_is_audited_without_personal_data(client, setup, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        archive(client, setup)
        archive(client, setup)  # idempotente: no genera un segundo evento
        reactivate(client, setup)

    messages = [r.getMessage() for r in caplog.records if r.name == "odontonet.audit"]
    assert [m.split()[0] for m in messages] == ["patient.archived", "patient.reactivated"]
    assert all(f"patient_id={setup['patient']}" in m for m in messages)
    assert not any(word in " ".join(messages) for word in ("Eva", "Luna", "eva@luna.com", "5555"))
