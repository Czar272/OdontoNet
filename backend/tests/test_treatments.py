"""Plan de tratamiento y seguimiento (ODON-158)."""
import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from app.auth.security import hash_password
from app.models import Doctor, Patient, Treatment, TreatmentStatusChange, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.records]

YESTERDAY = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)


@pytest.fixture
def setup(db, client):
    clinic, _, doctor = create_clinic_with_doctor(db, "Clinica Tratamientos", "doc@tratamientos-clinica.com")
    other_clinic, _, _ = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-tratamientos.com")
    admin = User(name="Admin Trat", email="admin@tratamientos-clinica.com", hashed_password=hash_password(PASSWORD), role="admin", clinic_id=clinic.id)
    reception = User(name="Recepción", email="recepcion@tratamientos-clinica.com", hashed_password=hash_password(PASSWORD), role="receptionist", clinic_id=clinic.id)
    db.add_all([admin, reception])
    db.flush()
    colleague_user = User(name="Dra. Colega", email="colega@tratamientos-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id)
    db.add(colleague_user)
    db.flush()
    db.add(Doctor(user_id=colleague_user.id, clinic_id=clinic.id))
    patient = Patient(first_name="Rosa", last_name="Vega", clinic_id=clinic.id)
    sibling = Patient(first_name="Otro", last_name="Paciente", clinic_id=clinic.id)
    other = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([patient, sibling, other])
    db.commit()

    headers = {
        "doctor": auth_headers(client, "doc@tratamientos-clinica.com"),
        "colleague": auth_headers(client, "colega@tratamientos-clinica.com"),
        "admin": auth_headers(client, "admin@tratamientos-clinica.com"),
        "receptionist": auth_headers(client, "recepcion@tratamientos-clinica.com"),
        "other": auth_headers(client, "doc@ajena-tratamientos.com"),
    }

    def visit(patient_id, reason="Control"):
        body = {"visit_at": YESTERDAY.isoformat(), "doctor_id": doctor.id, "reason": reason}
        response = client.post(f"/patients/{patient_id}/visits", json=body, headers=headers["doctor"])
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return {
        "patient": patient.id,
        "sibling": sibling.id,
        "other": other.id,
        "headers": headers,
        "visit": visit(patient.id, "Evaluación inicial"),
        "visit2": visit(patient.id, "Raspado"),
        "sibling_visit": visit(sibling.id),
    }


def url(patient_id, suffix=""):
    return f"/patients/{patient_id}/treatments{suffix}"


def create(client, setup, role="doctor", **body):
    data = {"procedure": "Raspado y alisado radicular", "tooth": 36, **body}
    return client.post(url(setup["patient"]), json=data, headers=setup["headers"][role])


def set_status(client, setup, treatment_id, status, role="doctor", **extra):
    return client.post(
        url(setup["patient"], f"/{treatment_id}/status"),
        json={"status": status, **extra},
        headers=setup["headers"][role],
    )


# --- Alta y lectura -------------------------------------------------------------


def test_doctor_proposes_a_treatment_linked_to_a_visit(client, setup):
    response = create(client, setup, proposed_visit_id=setup["visit"], planned_date="2026-12-15", notes="Por cuadrantes")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "proposed"
    assert body["tooth"] == 36
    assert body["planned_date"] == "2026-12-15"
    assert body["proposed_visit"]["id"] == setup["visit"]
    assert body["proposed_visit"]["reason"] == "Evaluación inicial"
    assert body["completed_visit"] is None
    assert body["created_by"]["name"] == "Dr. Clinica Tratamientos"


def test_creation_is_the_first_status_change(client, setup, db):
    treatment_id = create(client, setup).json()["id"]

    history = client.get(url(setup["patient"], f"/{treatment_id}/history"), headers=setup["headers"]["doctor"]).json()

    assert len(history) == 1
    assert history[0]["from_status"] is None
    assert history[0]["to_status"] == "proposed"


def test_only_procedure_is_required(client, setup):
    response = client.post(url(setup["patient"]), json={"procedure": "Profilaxis"}, headers=setup["headers"]["doctor"])

    assert response.status_code == 201
    assert response.json()["tooth"] is None
    assert response.json()["proposed_visit"] is None


def test_list_shows_pending_first(client, setup):
    proposed = create(client, setup, procedure="A").json()["id"]
    in_progress = create(client, setup, procedure="B").json()["id"]
    cancelled = create(client, setup, procedure="C").json()["id"]
    set_status(client, setup, in_progress, "accepted")
    set_status(client, setup, in_progress, "in_progress")
    set_status(client, setup, cancelled, "cancelled", reason="El paciente no aceptó")

    ids = [t["id"] for t in client.get(url(setup["patient"]), headers=setup["headers"]["doctor"]).json()]

    assert ids == [in_progress, proposed, cancelled]


# --- Validación -----------------------------------------------------------------------


@pytest.mark.parametrize("tooth", [0, 10, 19, 49, 56, 90, 100])
def test_invalid_fdi_tooth_is_422(client, setup, tooth):
    response = create(client, setup, tooth=tooth)

    assert response.status_code == 422
    assert "FDI" in response.json()["errors"][0]["message"]


@pytest.mark.parametrize("tooth", [11, 18, 48, 51, 55, 85])
def test_valid_fdi_teeth_including_deciduous(client, setup, tooth):
    assert create(client, setup, tooth=tooth).status_code == 201


@pytest.mark.parametrize("procedure", ["", "   ", "x" * 301])
def test_procedure_is_validated(client, setup, procedure):
    assert create(client, setup, procedure=procedure).status_code == 422


def test_proposed_visit_must_belong_to_the_patient(client, setup):
    response = create(client, setup, proposed_visit_id=setup["sibling_visit"])

    assert response.status_code == 422
    assert response.json() == {"detail": "La consulta de la propuesta no pertenece a este paciente."}


def test_voided_visit_cannot_be_linked(client, setup):
    client.post(url(setup["patient"]).replace("treatments", f"visits/{setup['visit']}/void"), json={"reason": "Error"}, headers=setup["headers"]["doctor"])

    response = create(client, setup, proposed_visit_id=setup["visit"])

    assert response.status_code == 422
    assert response.json() == {"detail": "La consulta de la propuesta está anulada."}


# --- Estados ----------------------------------------------------------------------------


def test_full_flow_records_every_change(client, setup):
    treatment_id = create(client, setup).json()["id"]

    set_status(client, setup, treatment_id, "accepted")
    set_status(client, setup, treatment_id, "in_progress", role="colleague")
    response = set_status(client, setup, treatment_id, "completed", role="admin", completed_visit_id=setup["visit2"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["completed_visit"]["id"] == setup["visit2"]
    assert body["updated_by"]["name"] == "Admin Trat"
    history = client.get(url(setup["patient"], f"/{treatment_id}/history"), headers=setup["headers"]["doctor"]).json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        ("in_progress", "completed"),
        ("accepted", "in_progress"),
        ("proposed", "accepted"),
        (None, "proposed"),
    ]
    assert [h["changed_by"]["name"] for h in history[:3]] == ["Admin Trat", "Dra. Colega", "Dr. Clinica Tratamientos"]


def test_accepted_can_be_completed_directly(client, setup):
    treatment_id = create(client, setup).json()["id"]
    set_status(client, setup, treatment_id, "accepted")

    assert set_status(client, setup, treatment_id, "completed", completed_visit_id=setup["visit"]).status_code == 200


@pytest.mark.parametrize(
    "path, target",
    [
        ([], "in_progress"),
        ([], "completed"),
        (["accepted"], "proposed"),
        (["accepted", "in_progress"], "accepted"),
    ],
)
def test_invalid_transitions_are_409(client, setup, path, target):
    treatment_id = create(client, setup).json()["id"]
    for step in path:
        set_status(client, setup, treatment_id, step)

    response = set_status(client, setup, treatment_id, target, completed_visit_id=setup["visit"])

    assert response.status_code == 409
    assert response.json()["detail"].startswith("No se puede pasar de")


def test_completing_requires_a_visit_of_the_patient(client, setup):
    treatment_id = create(client, setup).json()["id"]
    set_status(client, setup, treatment_id, "accepted")

    missing = set_status(client, setup, treatment_id, "completed")
    foreign = set_status(client, setup, treatment_id, "completed", completed_visit_id=setup["sibling_visit"])

    assert missing.status_code == 422
    assert missing.json() == {"detail": "Indica la consulta en que se realizó el tratamiento."}
    assert foreign.status_code == 422
    assert foreign.json() == {"detail": "La consulta de realización no pertenece a este paciente."}


def test_cancelling_requires_reason_and_keeps_it(client, setup):
    treatment_id = create(client, setup).json()["id"]

    without = set_status(client, setup, treatment_id, "cancelled", reason="  ")
    with_reason = set_status(client, setup, treatment_id, "cancelled", reason="El paciente prefirió otra opción")

    assert without.status_code == 422
    assert without.json() == {"detail": "Indica el motivo de la cancelación."}
    assert with_reason.status_code == 200
    assert with_reason.json()["status_reason"] == "El paciente prefirió otra opción"


@pytest.mark.parametrize("final", ["completed", "cancelled"])
def test_closed_treatments_cannot_change(client, setup, final):
    treatment_id = create(client, setup).json()["id"]
    set_status(client, setup, treatment_id, "accepted")
    set_status(client, setup, treatment_id, final, completed_visit_id=setup["visit"], reason="Motivo")

    edit = client.patch(url(setup["patient"], f"/{treatment_id}"), json={"notes": "x"}, headers=setup["headers"]["doctor"])
    move = set_status(client, setup, treatment_id, "in_progress")

    assert edit.status_code == 409
    assert move.status_code == 409


# --- Edición ------------------------------------------------------------------------------


def test_any_doctor_edits_and_is_recorded(client, setup):
    treatment_id = create(client, setup).json()["id"]

    response = client.patch(
        url(setup["patient"], f"/{treatment_id}"),
        json={"tooth": 46, "notes": "Cambio de pieza", "planned_date": "2027-01-10"},
        headers=setup["headers"]["colleague"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["tooth"], body["notes"], body["planned_date"]) == (46, "Cambio de pieza", "2027-01-10")
    assert body["updated_by"]["name"] == "Dra. Colega"
    assert body["created_by"]["name"] == "Dr. Clinica Tratamientos"


def test_edit_can_clear_optional_fields(client, setup):
    treatment_id = create(client, setup, proposed_visit_id=setup["visit"]).json()["id"]

    body = client.patch(
        url(setup["patient"], f"/{treatment_id}"),
        json={"tooth": None, "proposed_visit_id": None, "notes": ""},
        headers=setup["headers"]["doctor"],
    ).json()

    assert body["tooth"] is None
    assert body["proposed_visit"] is None
    assert body["notes"] is None


def test_edit_rejects_empty_procedure(client, setup):
    treatment_id = create(client, setup).json()["id"]

    response = client.patch(url(setup["patient"], f"/{treatment_id}"), json={"procedure": None}, headers=setup["headers"]["doctor"])

    assert response.status_code == 422
    assert response.json() == {"detail": "Indica el procedimiento."}


# --- Permisos y aislamiento -----------------------------------------------------------------


@pytest.mark.rbac
@pytest.mark.parametrize("method, suffix", [("get", ""), ("post", ""), ("get", "/1"), ("patch", "/1"), ("post", "/1/status"), ("get", "/1/history")])
def test_receptionist_has_no_access(client, setup, method, suffix):
    create(client, setup)

    kwargs = {"json": {"procedure": "x", "status": "accepted"}} if method != "get" else {}
    response = getattr(client, method)(url(setup["patient"], suffix), headers=setup["headers"]["receptionist"], **kwargs)

    assert response.status_code == 403


@pytest.mark.isolation
@pytest.mark.parametrize("suffix", ["", "/1", "/1/history"])
def test_other_clinic_gets_404(client, setup, suffix):
    create(client, setup)

    response = client.get(url(setup["patient"], suffix), headers=setup["headers"]["other"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Paciente no encontrado."}


@pytest.mark.isolation
def test_treatment_of_another_patient_is_404(client, setup):
    treatment_id = create(client, setup).json()["id"]

    response = client.get(url(setup["sibling"], f"/{treatment_id}"), headers=setup["headers"]["doctor"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Tratamiento no encontrado."}


@pytest.mark.patients
def test_archived_patient_is_read_only(client, setup, db):
    treatment_id = create(client, setup).json()["id"]
    db.query(Patient).filter(Patient.id == setup["patient"]).update({"archived_at": YESTERDAY})
    db.commit()

    assert create(client, setup).status_code == 409
    assert set_status(client, setup, treatment_id, "accepted").status_code == 409
    assert client.patch(url(setup["patient"], f"/{treatment_id}"), json={"notes": "x"}, headers=setup["headers"]["doctor"]).status_code == 409
    assert client.get(url(setup["patient"]), headers=setup["headers"]["doctor"]).status_code == 200


def test_database_requires_completed_visit(db, setup):
    treatment = db.query(Treatment).first() or None
    assert treatment is None
    patient = db.get(Patient, setup["patient"])
    doctor_user = db.query(User).filter(User.email == "doc@tratamientos-clinica.com").one()
    bad = Treatment(clinic_id=patient.clinic_id, patient_id=patient.id, procedure="x", status="completed", created_by_user_id=doctor_user.id, updated_by_user_id=doctor_user.id)
    db.add(bad)

    with pytest.raises(Exception, match="ck_treatments_completed_visit"):
        db.commit()
    db.rollback()


def test_audit_log_has_ids_but_no_clinical_content(client, setup, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        treatment_id = create(client, setup, procedure="Endodoncia molar").json()["id"]
        set_status(client, setup, treatment_id, "accepted")

    assert "treatment.created" in caplog.text
    assert "treatment.status_changed" in caplog.text
    assert "from=proposed to=accepted" in caplog.text
    assert "Endodoncia" not in caplog.text


def test_simultaneous_status_changes_apply_only_one(client, setup, db):
    """Completar y cancelar a la vez: el bloqueo de fila deja pasar solo uno."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient

    from app.main import app

    treatment_id = create(client, setup).json()["id"]
    set_status(client, setup, treatment_id, "accepted")
    attempts = [
        {"status": "completed", "completed_visit_id": setup["visit"]},
        {"status": "cancelled", "reason": "Cambio de plan"},
        {"status": "completed", "completed_visit_id": setup["visit2"]},
        {"status": "cancelled", "reason": "Otro motivo"},
    ]
    barrier = threading.Barrier(len(attempts))

    def attempt(body):
        with TestClient(app) as own_client:
            barrier.wait()
            return own_client.post(
                url(setup["patient"], f"/{treatment_id}/status"), json=body, headers=setup["headers"]["doctor"]
            ).status_code

    with ThreadPoolExecutor(max_workers=len(attempts)) as pool:
        codes = sorted(pool.map(attempt, attempts))

    assert codes == [200, 409, 409, 409]
    changes = db.query(TreatmentStatusChange).filter(TreatmentStatusChange.treatment_id == treatment_id).count()
    assert changes == 3  # alta, aceptado y un solo cierre
