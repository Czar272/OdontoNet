"""Consultas clínicas con revisiones y anulación (ODON-154)."""
import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from app.auth.security import hash_password
from app.models import ClinicalVisit, ClinicalVisitRevision, Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.records]

NOW = datetime.now(timezone.utc).replace(microsecond=0)
YESTERDAY = NOW - timedelta(days=1)


@pytest.fixture
def setup(db, client):
    clinic, author_user, author_doctor = create_clinic_with_doctor(db, "Clinica Consultas", "autor@consultas-clinica.com")
    other_clinic, _, other_doctor = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-consultas.com")

    colleague_user = User(name="Dra. Colega", email="colega@consultas-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id)
    admin = User(name="Admin Consultas", email="admin@consultas-clinica.com", hashed_password=hash_password(PASSWORD), role="admin", clinic_id=clinic.id)
    reception = User(name="Recepción", email="recepcion@consultas-clinica.com", hashed_password=hash_password(PASSWORD), role="receptionist", clinic_id=clinic.id)
    retired_user = User(name="Dr. Retirado", email="retirado@consultas-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id, is_active=False)
    # Recepción y admin primero: así los ids de usuario y de perfil de doctor no coinciden.
    db.add(admin)
    db.add(reception)
    db.flush()
    db.add_all([colleague_user, retired_user])
    db.flush()
    colleague = Doctor(user_id=colleague_user.id, clinic_id=clinic.id)
    retired = Doctor(user_id=retired_user.id, clinic_id=clinic.id)
    patient = Patient(first_name="Luis", last_name="Paz", clinic_id=clinic.id)
    other = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([colleague, retired, patient, other])
    db.commit()

    return {
        "patient": patient.id,
        "other": other.id,
        "doctor": author_doctor.id,
        "colleague": colleague.id,
        "retired": retired.id,
        "other_doctor": other_doctor.id,
        "author_user": author_user.id,
        "headers": {
            "author": auth_headers(client, "autor@consultas-clinica.com"),
            "colleague": auth_headers(client, "colega@consultas-clinica.com"),
            "admin": auth_headers(client, "admin@consultas-clinica.com"),
            "receptionist": auth_headers(client, "recepcion@consultas-clinica.com"),
            "other": auth_headers(client, "doc@ajena-consultas.com"),
        },
    }


def url(patient_id, suffix=""):
    return f"/patients/{patient_id}/visits{suffix}"


def content(setup, **changes):
    body = {
        "visit_at": YESTERDAY.isoformat(),
        "doctor_id": setup["doctor"],
        "reason": "Sangrado al cepillarse",
        "findings": "Inflamación gingival generalizada",
        "diagnosis": "Gingivitis inducida por placa",
        "procedures": "Profilaxis",
        "instructions": "Cepillado tres veces al día",
        "next_visit_date": (YESTERDAY + timedelta(days=90)).date().isoformat(),
    }
    body.update(changes)
    return body


def create(client, setup, role="author", **changes):
    return client.post(url(setup["patient"]), json=content(setup, **changes), headers=setup["headers"][role])


def update(client, setup, visit_id, base_revision=1, role="author", **changes):
    return client.put(
        url(setup["patient"], f"/{visit_id}"),
        json={**content(setup, **changes), "base_revision": base_revision},
        headers=setup["headers"][role],
    )


def void(client, setup, visit_id, role="author", reason="Registrada en el paciente equivocado"):
    return client.post(url(setup["patient"], f"/{visit_id}/void"), json={"reason": reason}, headers=setup["headers"][role])


# --- Alta y lectura -------------------------------------------------------------


def test_doctor_records_visit_linked_to_patient_and_doctor(client, setup):
    response = create(client, setup)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["patient_id"] == setup["patient"]
    assert body["doctor"] == {"id": setup["doctor"], "name": "Dr. Clinica Consultas"}
    assert body["revision"] == 1
    assert body["created_by"]["id"] == setup["author_user"]
    assert body["updated_by"] == body["created_by"]
    assert body["diagnosis"] == "Gingivitis inducida por placa"
    assert datetime.fromisoformat(body["visit_at"]) == YESTERDAY
    assert body["voided_at"] is None


def test_creation_stores_first_revision(client, setup, db):
    visit_id = create(client, setup).json()["id"]

    revisions = client.get(url(setup["patient"], f"/{visit_id}/revisions"), headers=setup["headers"]["author"]).json()

    assert [r["revision"] for r in revisions] == [1]
    assert revisions[0]["reason"] == "Sangrado al cepillarse"
    assert db.query(ClinicalVisitRevision).count() == 1


def test_list_is_newest_first_and_includes_voided(client, setup):
    older = create(client, setup, visit_at=(YESTERDAY - timedelta(days=30)).isoformat(), next_visit_date=None).json()["id"]
    newer = create(client, setup).json()["id"]
    void(client, setup, older)

    visits = client.get(url(setup["patient"]), headers=setup["headers"]["colleague"]).json()

    assert [v["id"] for v in visits] == [newer, older]
    assert visits[1]["void_reason"] == "Registrada en el paciente equivocado"


def test_only_date_doctor_and_reason_are_required(client, setup):
    body = {"visit_at": YESTERDAY.isoformat(), "doctor_id": setup["doctor"], "reason": "Control"}

    response = client.post(url(setup["patient"]), json=body, headers=setup["headers"]["author"])

    assert response.status_code == 201
    assert response.json()["findings"] is None
    assert response.json()["next_visit_date"] is None


def test_blank_texts_are_stored_as_null(client, setup):
    body = create(client, setup, findings="   ", diagnosis="").json()

    assert body["findings"] is None
    assert body["diagnosis"] is None


# --- Validación ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"reason": "  "}, "reason"),
        ({"reason": "x" * 501}, "reason"),
        ({"findings": "x" * 4001}, "findings"),
        ({"visit_at": "2026-11-01T10:00:00"}, "visit_at"),
        ({"doctor_id": None}, "doctor_id"),
    ],
)
def test_invalid_content_is_422(client, setup, changes, field):
    response = create(client, setup, **changes)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field


def test_future_visit_is_rejected(client, setup):
    response = create(client, setup, visit_at=(NOW + timedelta(hours=2)).isoformat(), next_visit_date=None)

    assert response.status_code == 422
    assert response.json() == {"detail": "La fecha de atención no puede estar en el futuro."}


def test_next_visit_must_be_after_the_visit_in_clinic_time(client, setup):
    # 23:00 en Guatemala = 05:00 UTC del día siguiente: la fecha que cuenta es la local.
    visit_at = datetime(2026, 10, 20, 5, 0, tzinfo=timezone.utc)

    same_day = create(client, setup, visit_at=visit_at.isoformat(), next_visit_date="2026-10-19")
    next_day = create(client, setup, visit_at=visit_at.isoformat(), next_visit_date="2026-10-20")

    assert same_day.status_code == 422
    assert same_day.json() == {"detail": "La próxima cita sugerida debe ser posterior a la consulta."}
    assert next_day.status_code == 201


@pytest.mark.doctors
def test_doctor_must_be_active_and_from_the_clinic(client, setup):
    inactive = create(client, setup, doctor_id=setup["retired"])
    foreign = create(client, setup, doctor_id=setup["other_doctor"])

    assert inactive.status_code == 422
    assert inactive.json() == {"detail": "El doctor seleccionado está inactivo."}
    assert foreign.status_code == 422
    assert foreign.json() == {"detail": "El doctor seleccionado no pertenece a la clínica."}


def test_a_visit_can_be_recorded_for_a_colleague(client, setup, db):
    body = create(client, setup, doctor_id=setup["colleague"]).json()

    # doctor.id es el id del perfil de doctor (el que se reenvía al editar), no el del usuario.
    assert body["doctor"] == {"id": setup["colleague"], "name": "Dra. Colega"}
    assert db.get(Doctor, setup["colleague"]).user_id != setup["colleague"]
    assert body["created_by"]["id"] == setup["author_user"]


# --- Edición con revisiones ------------------------------------------------------------


def test_doctor_returned_by_the_api_can_be_sent_back_on_edit(client, setup):
    created = create(client, setup, doctor_id=setup["colleague"]).json()

    response = update(client, setup, created["id"], doctor_id=created["doctor"]["id"], findings="Sin cambios de doctor")

    assert response.status_code == 200, response.text
    assert response.json()["doctor"]["id"] == setup["colleague"]
    revisions = client.get(url(setup["patient"], f"/{created['id']}/revisions"), headers=setup["headers"]["author"]).json()
    assert {r["doctor"]["id"] for r in revisions} == {setup["colleague"]}


def test_changing_the_doctor_is_reflected_in_the_response(client, setup):
    visit_id = create(client, setup).json()["id"]

    body = update(client, setup, visit_id, doctor_id=setup["colleague"]).json()

    assert body["doctor"] == {"id": setup["colleague"], "name": "Dra. Colega"}


def test_edit_creates_a_revision_and_keeps_the_previous_one(client, setup):
    visit_id = create(client, setup).json()["id"]

    response = update(client, setup, visit_id, diagnosis="Periodontitis estadio I")

    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert response.json()["diagnosis"] == "Periodontitis estadio I"
    revisions = client.get(url(setup["patient"], f"/{visit_id}/revisions"), headers=setup["headers"]["author"]).json()
    assert [r["revision"] for r in revisions] == [2, 1]
    assert revisions[1]["diagnosis"] == "Gingivitis inducida por placa"


def test_admin_edits_and_is_recorded_as_editor(client, setup):
    visit_id = create(client, setup).json()["id"]

    body = update(client, setup, visit_id, role="admin", instructions="Enjuague con clorhexidina").json()

    assert body["updated_by"]["name"] == "Admin Consultas"
    assert body["created_by"]["id"] == setup["author_user"]


def test_saving_without_changes_does_not_create_a_revision(client, setup):
    visit_id = create(client, setup).json()["id"]

    body = update(client, setup, visit_id).json()

    assert body["revision"] == 1


def test_stale_revision_is_409(client, setup):
    visit_id = create(client, setup).json()["id"]
    update(client, setup, visit_id, role="admin", findings="Cambio del admin")

    response = update(client, setup, visit_id, base_revision=1, findings="Pisaría")

    assert response.status_code == 409
    assert response.json()["current_revision"] == 2


@pytest.mark.doctors
def test_keeping_a_now_inactive_doctor_on_edit_is_allowed(client, setup, db):
    visit_id = create(client, setup, doctor_id=setup["colleague"]).json()["id"]
    colleague_user_id = db.get(Doctor, setup["colleague"]).user_id
    db.query(User).filter(User.id == colleague_user_id).update({"is_active": False})
    db.commit()

    response = update(client, setup, visit_id, doctor_id=setup["colleague"], instructions="Sin cambios de doctor")

    assert response.status_code == 200


# --- Anulación ----------------------------------------------------------------------------


def test_void_keeps_the_visit_with_reason_and_author(client, setup, db):
    visit_id = create(client, setup).json()["id"]

    body = void(client, setup, visit_id).json()

    assert body["voided_at"] is not None
    assert body["voided_by"]["id"] == setup["author_user"]
    assert body["void_reason"] == "Registrada en el paciente equivocado"
    assert db.query(ClinicalVisit).count() == 1


def test_void_requires_reason(client, setup):
    visit_id = create(client, setup).json()["id"]

    assert void(client, setup, visit_id, reason=" ").status_code == 422


def test_voided_visit_cannot_be_edited_or_voided_again(client, setup):
    visit_id = create(client, setup).json()["id"]
    void(client, setup, visit_id)

    assert update(client, setup, visit_id, findings="x").status_code == 409
    assert void(client, setup, visit_id).status_code == 409


# --- Permisos y aislamiento -----------------------------------------------------------------


@pytest.mark.rbac
def test_other_doctor_reads_but_cannot_edit_or_void(client, setup):
    visit_id = create(client, setup).json()["id"]

    assert client.get(url(setup["patient"], f"/{visit_id}"), headers=setup["headers"]["colleague"]).status_code == 200
    edit = update(client, setup, visit_id, role="colleague", findings="x")
    assert edit.status_code == 403
    assert edit.json() == {"detail": "Solo quien registró la consulta o administración pueden modificarla."}
    assert void(client, setup, visit_id, role="colleague").status_code == 403


@pytest.mark.rbac
def test_admin_can_void(client, setup):
    visit_id = create(client, setup).json()["id"]

    assert void(client, setup, visit_id, role="admin").status_code == 200


@pytest.mark.rbac
@pytest.mark.parametrize("method, suffix", [("get", ""), ("post", ""), ("get", "/1"), ("get", "/1/revisions")])
def test_receptionist_has_no_access(client, setup, method, suffix):
    create(client, setup)

    kwargs = {"json": content(setup)} if method == "post" else {}
    response = getattr(client, method)(url(setup["patient"], suffix), headers=setup["headers"]["receptionist"], **kwargs)

    assert response.status_code == 403


@pytest.mark.isolation
@pytest.mark.parametrize("suffix", ["", "/1", "/1/revisions"])
def test_other_clinic_gets_404(client, setup, suffix):
    create(client, setup)

    response = client.get(url(setup["patient"], suffix), headers=setup["headers"]["other"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Paciente no encontrado."}


@pytest.mark.isolation
def test_visit_of_another_patient_is_404(client, setup, db):
    visit_id = create(client, setup).json()["id"]
    sibling = Patient(first_name="Otro", last_name="Paciente", clinic_id=db.get(Patient, setup["patient"]).clinic_id)
    db.add(sibling)
    db.commit()

    response = client.get(url(sibling.id, f"/{visit_id}"), headers=setup["headers"]["author"])

    assert response.status_code == 404
    assert response.json() == {"detail": "Consulta no encontrada."}


@pytest.mark.patients
def test_archived_patient_is_read_only(client, setup, db):
    visit_id = create(client, setup).json()["id"]
    db.query(Patient).filter(Patient.id == setup["patient"]).update({"archived_at": NOW})
    db.commit()

    assert create(client, setup).status_code == 409
    assert update(client, setup, visit_id, findings="x").status_code == 409
    assert void(client, setup, visit_id).status_code == 409
    assert client.get(url(setup["patient"]), headers=setup["headers"]["author"]).status_code == 200


def test_audit_log_has_ids_but_no_clinical_content(client, setup, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        visit_id = create(client, setup).json()["id"]
        update(client, setup, visit_id, diagnosis="Periodontitis")

    assert "clinical_visit.created" in caplog.text
    assert "clinical_visit.updated" in caplog.text
    assert "fields=diagnosis" in caplog.text
    assert "Gingivitis" not in caplog.text
    assert "Periodontitis" not in caplog.text
