"""Historia médica y odontológica versionada (ODON-150)."""
import logging
from datetime import datetime, timezone

import pytest

from app.auth.security import hash_password
from app.models import Patient, PatientMedicalHistory, User
from app.models.medical_history import MEDICAL_CONDITIONS
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.records]


@pytest.fixture
def setup(db, client):
    clinic, doctor_user, _ = create_clinic_with_doctor(db, "Clinica Historia", "doc@historia-clinica.com")
    other_clinic, _, _ = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-clinica.com")
    for role in ("admin", "receptionist"):
        db.add(User(name=f"{role} Historia", email=f"{role}@historia-clinica.com", hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic.id))
    patient = Patient(first_name="Ana", last_name="Ruiz", clinic_id=clinic.id)
    other = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([patient, other])
    db.commit()
    return {
        "patient": patient.id,
        "other": other.id,
        "doctor_user": doctor_user.id,
        "headers": {
            "doctor": auth_headers(client, "doc@historia-clinica.com"),
            "admin": auth_headers(client, "admin@historia-clinica.com"),
            "receptionist": auth_headers(client, "receptionist@historia-clinica.com"),
            "other": auth_headers(client, "doc@ajena-clinica.com"),
        },
    }


def url(patient_id, suffix=""):
    return f"/patients/{patient_id}/medical-history{suffix}"


FULL = {
    "conditions": {
        "diabetes": {"present": True, "detail": "Tipo 2, metformina"},
        "hypertension": {"present": False},
    },
    "allergies": "Penicilina",
    "current_medications": "Metformina 850 mg",
    "smoking_status": "current",
    "cigarettes_per_day": 10,
    "alcohol": False,
    "bruxism": True,
    "chief_complaint": "Sangrado al cepillarse",
    "last_dental_visit": "Hace 2 años",
    "brushing_per_day": 2,
    "uses_floss": False,
    "gum_bleeding": True,
    "notes": "Paciente ansiosa",
}


def save(client, setup, data=None, role="doctor", base_version=None, patient="patient"):
    body = {**(FULL if data is None else data), "base_version": base_version}
    return client.post(url(setup[patient]), json=body, headers=setup["headers"][role])


# --- Lectura y creación -------------------------------------------------------


def test_patient_without_history_returns_null(client, setup):
    response = client.get(url(setup["patient"]), headers=setup["headers"]["doctor"])

    assert response.status_code == 200
    assert response.json() is None
    assert client.get(url(setup["patient"], "/versions"), headers=setup["headers"]["doctor"]).json() == []


def test_doctor_creates_first_version_with_author_and_date(client, setup):
    before = datetime.now(timezone.utc)
    response = save(client, setup)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["version"] == 1
    assert body["created_by"] == {"id": setup["doctor_user"], "name": "Dr. Clinica Historia"}
    assert datetime.fromisoformat(body["created_at"]) >= before.replace(microsecond=0)
    assert body["allergies"] == "Penicilina"
    assert body["cigarettes_per_day"] == 10
    assert body["conditions"]["diabetes"] == {"present": True, "detail": "Tipo 2, metformina"}


def test_conditions_always_come_complete_and_in_order(client, setup):
    body = save(client, setup).json()

    assert list(body["conditions"]) == list(MEDICAL_CONDITIONS)
    assert body["conditions"]["hypertension"] == {"present": False, "detail": None}
    assert body["conditions"]["heart_disease"] == {"present": None, "detail": None}


def test_current_returns_latest_version(client, setup):
    save(client, setup)
    save(client, setup, {**FULL, "allergies": "Penicilina y látex"}, base_version=1)

    body = client.get(url(setup["patient"]), headers=setup["headers"]["doctor"]).json()

    assert body["version"] == 2
    assert body["allergies"] == "Penicilina y látex"


def test_previous_versions_are_kept_unchanged(client, setup, db):
    save(client, setup)
    save(client, setup, {**FULL, "allergies": "Ninguna"}, role="admin", base_version=1)

    old = client.get(url(setup["patient"], "/versions/1"), headers=setup["headers"]["doctor"]).json()
    versions = client.get(url(setup["patient"], "/versions"), headers=setup["headers"]["doctor"]).json()

    assert old["allergies"] == "Penicilina"
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["created_by"]["name"] == "admin Historia"
    assert versions[1]["created_by"]["name"] == "Dr. Clinica Historia"
    assert db.query(PatientMedicalHistory).count() == 2


def test_unknown_version_is_404(client, setup):
    save(client, setup)

    response = client.get(url(setup["patient"], "/versions/9"), headers=setup["headers"]["doctor"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Versión no encontrada."}


def test_empty_history_is_valid_and_blank_texts_are_null(client, setup):
    response = save(client, setup, {"allergies": "   ", "notes": ""})

    assert response.status_code == 201
    body = response.json()
    assert body["allergies"] is None
    assert body["notes"] is None
    assert all(entry["present"] is None for entry in body["conditions"].values())


# --- Conflictos de edición -----------------------------------------------------


def test_stale_base_version_is_409(client, setup):
    save(client, setup)
    save(client, setup, base_version=1)

    response = save(client, setup, {**FULL, "notes": "pisaría"}, base_version=1)

    assert response.status_code == 409
    assert response.json()["current_version"] == 2
    assert "cambió mientras la editabas" in response.json()["detail"]


def test_first_save_requires_null_base_version(client, setup):
    save(client, setup)

    response = save(client, setup, base_version=None)

    assert response.status_code == 409
    assert response.json()["current_version"] == 1


def test_base_version_ahead_of_current_is_409(client, setup):
    response = save(client, setup, base_version=3)

    assert response.status_code == 409
    assert response.json()["current_version"] is None


@pytest.mark.patients
def test_archived_patient_history_is_read_only(client, setup, db):
    save(client, setup)
    db.query(Patient).filter(Patient.id == setup["patient"]).update({"archived_at": datetime.now(timezone.utc)})
    db.commit()

    response = save(client, setup, base_version=1)

    assert response.status_code == 409
    assert "archivado" in response.json()["detail"]
    assert client.get(url(setup["patient"]), headers=setup["headers"]["doctor"]).json()["version"] == 1


# --- Validación ----------------------------------------------------------------


def test_unknown_condition_is_422(client, setup):
    response = save(client, setup, {"conditions": {"gripe": {"present": True}}})

    assert response.status_code == 422
    assert response.json()["errors"][0] == {"field": "conditions", "message": "Condición desconocida: gripe."}


def test_cigarettes_require_current_smoker(client, setup):
    response = save(client, setup, {"smoking_status": "former", "cigarettes_per_day": 5})

    assert response.status_code == 422
    assert "solo si el paciente fuma actualmente" in response.json()["errors"][0]["message"]


@pytest.mark.parametrize(
    "field, value",
    [
        ("smoking_status", "a veces"),
        ("cigarettes_per_day", 0),
        ("cigarettes_per_day", 500),
        ("brushing_per_day", 11),
        ("brushing_per_day", -1),
        ("allergies", "x" * 2001),
        ("last_dental_visit", "x" * 81),
    ],
)
def test_out_of_range_values_are_422(client, setup, field, value):
    data = {field: value}
    if field == "cigarettes_per_day":
        data["smoking_status"] = "current"

    response = save(client, setup, data)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field


def test_condition_detail_is_limited(client, setup):
    response = save(client, setup, {"conditions": {"diabetes": {"present": True, "detail": "x" * 501}}})

    assert response.status_code == 422


# --- Permisos y aislamiento ------------------------------------------------------


@pytest.mark.rbac
@pytest.mark.parametrize("role", ["admin", "doctor"])
def test_admin_and_doctor_can_write(client, setup, role):
    assert save(client, setup, role=role).status_code == 201


@pytest.mark.rbac
def test_receptionist_reads_everything_but_cannot_write(client, setup):
    save(client, setup)
    headers = setup["headers"]["receptionist"]

    response = save(client, setup, role="receptionist", base_version=1)

    assert response.status_code == 403
    assert client.get(url(setup["patient"]), headers=headers).json()["allergies"] == "Penicilina"
    assert client.get(url(setup["patient"], "/versions"), headers=headers).status_code == 200
    assert client.get(url(setup["patient"], "/versions/1"), headers=headers).status_code == 200


@pytest.mark.isolation
@pytest.mark.parametrize("suffix", ["", "/versions", "/versions/1"])
def test_other_clinic_gets_404_on_read(client, setup, suffix):
    save(client, setup)

    response = client.get(url(setup["patient"], suffix), headers=setup["headers"]["other"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Paciente no encontrado."}


@pytest.mark.isolation
def test_other_clinic_cannot_write(client, setup, db):
    response = client.post(url(setup["patient"]), json={**FULL, "base_version": None}, headers=setup["headers"]["other"])

    assert response.status_code == 404
    assert db.query(PatientMedicalHistory).count() == 0


@pytest.mark.isolation
def test_history_is_stored_in_patient_clinic(client, setup, db):
    save(client, setup)

    stored = db.query(PatientMedicalHistory).one()
    patient = db.get(Patient, setup["patient"])
    assert stored.clinic_id == patient.clinic_id


def test_requires_session(client, setup):
    assert client.get(url(setup["patient"])).status_code == 401


def test_audit_log_has_ids_but_no_clinical_content(client, setup, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        save(client, setup)

    assert "medical_history.created" in caplog.text
    assert f"patient_id={setup['patient']}" in caplog.text
    assert "Penicilina" not in caplog.text
