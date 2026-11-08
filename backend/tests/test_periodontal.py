"""Periodontograma manual: modelo, validación, borradores, finalización y acceso (ODON-9)."""
import logging
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.security import hash_password
from app.models import (
    Patient,
    PeriodontalExam,
    PeriodontalExamRevision,
    PeriodontalSite,
    PeriodontalTooth,
    User,
)
from app.models.periodontal import PERMANENT_TEETH, SITES
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.periodontal]

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
def setup(db, client):
    clinic, _, doctor = create_clinic_with_doctor(db, "Clinica Perio", "autor@perio-clinica.com")
    other_clinic, _, _ = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-perio.com")
    db.add_all([
        User(name="Dra. Colega", email="colega@perio-clinica.com", hashed_password=hash_password(PASSWORD),
             role="doctor", clinic_id=clinic.id),
        User(name="Admin Perio", email="admin@perio-clinica.com", hashed_password=hash_password(PASSWORD),
             role="admin", clinic_id=clinic.id),
        User(name="Recepción", email="recepcion@perio-clinica.com", hashed_password=hash_password(PASSWORD),
             role="receptionist", clinic_id=clinic.id),
        User(name="Admin Ajena", email="admin@ajena-perio.com", hashed_password=hash_password(PASSWORD),
             role="admin", clinic_id=other_clinic.id),
    ])
    patient = Patient(first_name="Ana", last_name="Ríos", clinic_id=clinic.id)
    sibling = Patient(first_name="Otro", last_name="Paciente", clinic_id=clinic.id)
    other = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([patient, sibling, other])
    db.commit()

    headers = {
        "author": auth_headers(client, "autor@perio-clinica.com"),
        "colleague": auth_headers(client, "colega@perio-clinica.com"),
        "admin": auth_headers(client, "admin@perio-clinica.com"),
        "receptionist": auth_headers(client, "recepcion@perio-clinica.com"),
        "other": auth_headers(client, "doc@ajena-perio.com"),
        "other_admin": auth_headers(client, "admin@ajena-perio.com"),
    }
    visits = {}
    for key, patient_id in (("visit", patient.id), ("sibling_visit", sibling.id)):
        response = client.post(
            f"/patients/{patient_id}/visits",
            json={"visit_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                  "doctor_id": doctor.id, "reason": "Evaluación periodontal"},
            headers=headers["author"],
        )
        assert response.status_code == 201, response.text
        visits[key] = response.json()["id"]
    return {"db": db, "patient": patient.id, "other": other.id, "headers": headers, **visits}


def url(setup, suffix="", patient_id=None):
    return f"/patients/{patient_id or setup['patient']}/periodontal-exams{suffix}"


def chart(**overrides):
    """Un examen pequeño: 16 con mediciones completas, 21 implante, 38 ausente."""
    body = {
        "exam_date": YESTERDAY.isoformat(),
        "notes": "Control semestral",
        "teeth": [
            {
                "tooth": 16, "mobility": 1, "furcation": {"b": 2, "mp": 1},
                "sites": {
                    "mb": {"probing_depth": 5, "gingival_margin": -2, "bleeding": True},
                    "b": {"probing_depth": 3, "gingival_margin": 0, "plaque": True},
                    "db": {"probing_depth": 4, "gingival_margin": -1, "bleeding": True, "suppuration": True},
                    "ml": {"probing_depth": 2, "gingival_margin": 1},
                },
            },
            {"tooth": 21, "implant": True, "sites": {"b": {"probing_depth": 2, "gingival_margin": 0}}},
            {"tooth": 38, "missing": True},
        ],
    }
    body.update(overrides)
    return body


def create(client, setup, role="author", **overrides):
    return client.post(url(setup), json=chart(**overrides), headers=setup["headers"][role])


@pytest.fixture
def exam(setup, client):
    response = create(client, setup)
    assert response.status_code == 201, response.text
    return response.json()


def save(client, setup, exam, role="author", **overrides):
    body = {**chart(**overrides), "base_revision": overrides.pop("base_revision", exam["revision"])}
    return client.put(url(setup, f"/{exam['id']}"), json=body, headers=setup["headers"][role])


def tooth(response_json, number):
    return next(t for t in response_json["teeth"] if t["tooth"] == number)


# --- Modelo -------------------------------------------------------------------


def test_new_exam_has_all_permanent_teeth_and_six_sites(exam, setup):
    db = setup["db"]
    assert db.query(PeriodontalTooth).filter_by(exam_id=exam["id"]).count() == 32
    assert db.query(PeriodontalSite).filter_by(exam_id=exam["id"]).count() == 32 * 6
    assert [t["tooth"] for t in exam["teeth"]] == list(PERMANENT_TEETH)
    assert all(list(t["sites"]) == list(SITES) for t in exam["teeth"])


def test_exam_records_date_patient_author_and_draft_status(exam, setup):
    assert exam["exam_date"] == YESTERDAY.isoformat()
    assert exam["patient_id"] == setup["patient"]
    author = setup["db"].query(User).filter_by(email="autor@perio-clinica.com").one()
    assert exam["created_by"] == {"id": author.id, "name": author.name}
    assert exam["status"] == "draft"
    assert exam["revision"] == 1
    assert exam["finalized_at"] is None


def test_measurements_are_stored_per_site_with_computed_attachment_level(exam):
    t16 = tooth(exam, 16)
    assert t16["mobility"] == 1
    assert t16["furcation"] == {"b": 2, "mp": 1, "dp": None, "l": None}
    mb = t16["sites"]["mb"]
    assert mb == {"probing_depth": 5, "gingival_margin": -2, "attachment_level": 7,
                  "bleeding": True, "suppuration": False, "plaque": False, "source": "manual"}
    assert t16["sites"]["ml"]["attachment_level"] == 1  # agrandamiento: NIC = 2 − 1
    assert t16["sites"]["dl"] == {"probing_depth": None, "gingival_margin": None, "attachment_level": None,
                                  "bleeding": False, "suppuration": False, "plaque": False, "source": "manual"}
    assert tooth(exam, 21)["implant"] is True
    assert tooth(exam, 38)["missing"] is True


def test_every_measurement_is_marked_manual(exam, setup):
    db = setup["db"]
    sources = {row.source for row in db.query(PeriodontalSite).filter_by(exam_id=exam["id"])}
    sources |= {row.source for row in db.query(PeriodontalTooth).filter_by(exam_id=exam["id"])}
    assert sources == {"manual"}


def test_summary_is_descriptive_and_excludes_missing_teeth(exam):
    summary = exam["summary"]
    # 5 sitios con sondaje: 16 mb/b/db/ml y 21 b.
    assert summary["measured_sites"] == 5
    assert summary["present_teeth"] == 31
    assert summary["mean_probing_depth"] == round((5 + 3 + 4 + 2 + 2) / 5, 2)
    assert summary["mean_attachment_level"] == round((7 + 3 + 5 + 1 + 2) / 5, 2)
    assert summary["bleeding_pct"] == 40.0
    assert summary["plaque_pct"] == 20.0
    assert summary["deep_sites_pct"] == 40.0  # 5 y 4 mm


def test_empty_exam_has_empty_summary(setup, client):
    body = create(client, setup, teeth=[], notes=None).json()
    assert body["summary"]["measured_sites"] == 0
    assert body["summary"]["mean_probing_depth"] is None
    assert body["summary"]["bleeding_pct"] is None


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE periodontal_sites SET probing_depth = 16 WHERE exam_id = :id AND tooth = 11 AND site = 'b'",
        "UPDATE periodontal_sites SET gingival_margin = 6 WHERE exam_id = :id AND tooth = 11 AND site = 'b'",
        "UPDATE periodontal_sites SET gingival_margin = -16 WHERE exam_id = :id AND tooth = 11 AND site = 'b'",
        "UPDATE periodontal_sites SET site = 'x' WHERE exam_id = :id AND tooth = 11 AND site = 'b'",
        "UPDATE periodontal_sites SET source = 'ai' WHERE exam_id = :id AND tooth = 11 AND site = 'b'",
        "UPDATE periodontal_teeth SET tooth = 55 WHERE exam_id = :id AND tooth = 11",
        "UPDATE periodontal_teeth SET mobility = 4 WHERE exam_id = :id AND tooth = 11",
        "UPDATE periodontal_teeth SET missing = true, implant = true WHERE exam_id = :id AND tooth = 11",
        "UPDATE periodontal_teeth SET missing = true, mobility = 2 WHERE exam_id = :id AND tooth = 11",
        "UPDATE periodontal_teeth SET missing = true, furcation_b = 3 WHERE exam_id = :id AND tooth = 46",
        "UPDATE periodontal_teeth SET implant = true, furcation_b = 2 WHERE exam_id = :id AND tooth = 46",
        "UPDATE periodontal_teeth SET furcation_b = 1 WHERE exam_id = :id AND tooth = 11",
        "UPDATE periodontal_teeth SET furcation_mp = 1 WHERE exam_id = :id AND tooth = 46",
        "UPDATE periodontal_teeth SET furcation_l = 1 WHERE exam_id = :id AND tooth = 16",
        "UPDATE periodontal_teeth SET furcation_b = 4 WHERE exam_id = :id AND tooth = 16",
        "UPDATE periodontal_exams SET status = 'final' WHERE id = :id",
        "UPDATE periodontal_exams SET voided_at = now() WHERE id = :id",
        "INSERT INTO periodontal_sites (clinic_id, exam_id, tooth, site) "
        "SELECT clinic_id, exam_id, tooth, site FROM periodontal_sites WHERE exam_id = :id LIMIT 1",
    ],
)
def test_database_rejects_inconsistent_values(exam, setup, sql):
    db = setup["db"]
    with pytest.raises(IntegrityError):
        db.execute(text(sql), {"id": exam["id"]})
        db.commit()
    db.rollback()


def test_rows_must_belong_to_the_exam_clinic(exam, setup):
    db = setup["db"]
    other_clinic = db.get(Patient, setup["other"]).clinic_id
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE periodontal_sites SET clinic_id = :c WHERE exam_id = :id"),
                   {"c": other_clinic, "id": exam["id"]})
        db.commit()
    db.rollback()


# --- Validación de la API -----------------------------------------------------


@pytest.mark.parametrize(
    "teeth",
    [
        [{"tooth": 55}],  # temporal
        [{"tooth": 19}],
        [{"tooth": 11, "sites": {"x": {"probing_depth": 2}}}],
        [{"tooth": 11, "sites": {"b": {"probing_depth": 16}}}],
        [{"tooth": 11, "sites": {"b": {"probing_depth": -1}}}],
        [{"tooth": 11, "sites": {"b": {"gingival_margin": 6}}}],
        [{"tooth": 11, "sites": {"b": {"gingival_margin": -16}}}],
        [{"tooth": 11, "mobility": 4}],
        [{"tooth": 11, "furcation": {"b": 1}}],
        [{"tooth": 46, "furcation": {"mp": 1}}],
        [{"tooth": 16, "furcation": {"l": 1}}],
        [{"tooth": 16, "furcation": {"b": 4}}],
        [{"tooth": 11, "missing": True, "implant": True}],
        [{"tooth": 11, "missing": True, "mobility": 1}],
        [{"tooth": 11, "missing": True, "sites": {"b": {"probing_depth": 3}}}],
        [{"tooth": 46, "implant": True, "furcation": {"b": 1}}],
        [{"tooth": 11}, {"tooth": 11}],
        [{"tooth": 11, "note": "x" * 501}],
    ],
)
def test_invalid_chart_is_rejected(setup, client, teeth):
    response = create(client, setup, teeth=teeth)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]


def test_exam_date_cannot_be_in_the_future(setup, client):
    response = create(client, setup, exam_date=(TODAY + timedelta(days=2)).isoformat())
    assert response.status_code == 422
    assert "futura" in response.json()["detail"]


def test_visit_must_belong_to_the_patient_and_be_active(setup, client):
    assert create(client, setup, clinical_visit_id=setup["sibling_visit"]).status_code == 422
    assert create(client, setup, clinical_visit_id=setup["visit"]).status_code == 201

    client.post(f"/patients/{setup['patient']}/visits/{setup['visit']}/void", json={"reason": "Error"},
                headers=setup["headers"]["author"])
    response = create(client, setup, clinical_visit_id=setup["visit"])
    assert response.status_code == 422
    assert "anulada" in response.json()["detail"]


def test_draft_keeps_a_visit_voided_later(setup, client):
    exam = create(client, setup, clinical_visit_id=setup["visit"]).json()
    client.post(f"/patients/{setup['patient']}/visits/{setup['visit']}/void", json={"reason": "Error"},
                headers=setup["headers"]["author"])
    response = save(client, setup, exam, clinical_visit_id=setup["visit"], notes="Cambio")
    assert response.status_code == 200, response.text
    assert response.json()["clinical_visit"]["id"] == setup["visit"]


# --- Borrador: guardado con revisiones -----------------------------------------


def test_saving_the_draft_creates_a_revision_with_a_full_snapshot(exam, setup, client):
    teeth = chart()["teeth"]
    teeth[0]["sites"]["mb"]["probing_depth"] = 6
    response = save(client, setup, exam, teeth=teeth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert tooth(body, 16)["sites"]["mb"]["probing_depth"] == 6

    db = setup["db"]
    revisions = db.query(PeriodontalExamRevision).filter_by(exam_id=exam["id"]).order_by(
        PeriodontalExamRevision.revision).all()
    assert [rev.revision for rev in revisions] == [1, 2]
    first = next(t for t in revisions[0].data["teeth"] if t["tooth"] == 16)
    second = next(t for t in revisions[1].data["teeth"] if t["tooth"] == 16)
    assert first["sites"]["mb"]["probing_depth"] == 5
    assert second["sites"]["mb"]["probing_depth"] == 6
    assert len(revisions[1].data["teeth"]) == 32

    listed = client.get(url(setup, f"/{exam['id']}/revisions"), headers=setup["headers"]["colleague"]).json()
    assert [rev["revision"] for rev in listed] == [2, 1]


def test_saving_without_changes_does_not_create_a_revision(exam, setup, client):
    response = save(client, setup, exam)
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert setup["db"].query(PeriodontalExamRevision).filter_by(exam_id=exam["id"]).count() == 1


def test_stale_base_revision_is_a_conflict(exam, setup, client):
    assert save(client, setup, exam, notes="Primero").status_code == 200
    response = save(client, setup, exam, notes="Segundo", base_revision=1)
    assert response.status_code == 409
    assert response.json()["current_revision"] == 2


def test_teeth_left_out_of_the_payload_are_cleared(exam, setup, client):
    response = save(client, setup, exam, teeth=[{"tooth": 21, "implant": True}])
    assert response.status_code == 200
    body = response.json()
    assert tooth(body, 16)["sites"]["mb"]["probing_depth"] is None
    assert tooth(body, 38)["missing"] is False


def test_only_the_author_or_admin_edits_the_draft(exam, setup, client):
    assert save(client, setup, exam, role="colleague", notes="x").status_code == 403
    response = save(client, setup, exam, role="admin", notes="Revisado por administración")
    assert response.status_code == 200
    # Cualquier doctor de la clínica lo puede leer.
    assert client.get(url(setup, f"/{exam['id']}"), headers=setup["headers"]["colleague"]).status_code == 200


# --- Finalización y anulación --------------------------------------------------


def test_finalize_makes_the_exam_immutable(exam, setup, client):
    response = client.post(url(setup, f"/{exam['id']}/finalize"), json={"base_revision": 1},
                           headers=setup["headers"]["author"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "final"
    assert body["finalized_by"]["id"] == exam["created_by"]["id"]

    response = save(client, setup, body, notes="Tarde")
    assert response.status_code == 409
    assert "Anúlalo" in response.json()["detail"]
    again = client.post(url(setup, f"/{exam['id']}/finalize"), json={"base_revision": 1},
                        headers=setup["headers"]["author"])
    assert again.status_code == 409


def test_finalize_requires_a_probing_depth_and_the_current_revision(setup, client):
    empty = create(client, setup, teeth=[{"tooth": 38, "missing": True}]).json()
    response = client.post(url(setup, f"/{empty['id']}/finalize"), json={"base_revision": 1},
                           headers=setup["headers"]["author"])
    assert response.status_code == 422

    exam = create(client, setup).json()
    save(client, setup, exam, notes="Cambio")
    response = client.post(url(setup, f"/{exam['id']}/finalize"), json={"base_revision": 1},
                           headers=setup["headers"]["author"])
    assert response.status_code == 409
    assert response.json()["current_revision"] == 2


def test_admin_creates_and_finalizes_any_draft(exam, setup, client):
    assert create(client, setup, role="admin").status_code == 201
    response = client.post(url(setup, f"/{exam['id']}/finalize"), json={"base_revision": 1},
                           headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["finalized_by"]["name"] == "Admin Perio"
    assert body["updated_at"] == body["finalized_at"]


def test_colleague_cannot_finalize_or_void(exam, setup, client):
    path = url(setup, f"/{exam['id']}")
    assert client.post(f"{path}/finalize", json={"base_revision": 1},
                       headers=setup["headers"]["colleague"]).status_code == 403
    assert client.post(f"{path}/void", json={"reason": "x"}, headers=setup["headers"]["colleague"]).status_code == 403


def test_void_keeps_the_exam_with_reason_and_blocks_changes(exam, setup, client):
    response = client.post(url(setup, f"/{exam['id']}/void"), json={"reason": "  Paciente equivocado "},
                           headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["void_reason"] == "Paciente equivocado"
    assert body["voided_by"]["name"] == "Admin Perio"

    assert save(client, setup, exam, notes="x").status_code == 409
    assert client.post(url(setup, f"/{exam['id']}/void"), json={"reason": "x"},
                       headers=setup["headers"]["admin"]).status_code == 409
    listed = client.get(url(setup), headers=setup["headers"]["author"]).json()
    assert [item["id"] for item in listed] == [exam["id"]]
    assert setup["db"].query(PeriodontalExam).count() == 1


def test_void_requires_a_reason(exam, setup, client):
    response = client.post(url(setup, f"/{exam['id']}/void"), json={"reason": "  "},
                           headers=setup["headers"]["author"])
    assert response.status_code == 422


def test_archived_patient_is_read_only(exam, setup, client):
    db = setup["db"]
    db.get(Patient, setup["patient"]).archived_at = datetime.now(timezone.utc)
    db.commit()
    assert create(client, setup).status_code == 409
    assert save(client, setup, exam, notes="x").status_code == 409
    assert client.post(url(setup, f"/{exam['id']}/finalize"), json={"base_revision": 1},
                       headers=setup["headers"]["author"]).status_code == 409
    assert client.post(url(setup, f"/{exam['id']}/void"), json={"reason": "x"},
                       headers=setup["headers"]["author"]).status_code == 409
    assert client.get(url(setup, f"/{exam['id']}"), headers=setup["headers"]["author"]).status_code == 200


def test_list_is_newest_first_with_summary(setup, client):
    older = create(client, setup, exam_date=(TODAY - timedelta(days=30)).isoformat()).json()
    newer = create(client, setup).json()
    listed = client.get(url(setup), headers=setup["headers"]["colleague"]).json()
    assert [item["id"] for item in listed] == [newer["id"], older["id"]]
    assert "teeth" not in listed[0]
    assert listed[0]["summary"]["measured_sites"] == 5


# --- Aislamiento y permisos ----------------------------------------------------


@pytest.mark.isolation
@pytest.mark.parametrize("role", ["other", "other_admin"])
def test_other_clinic_gets_404_everywhere(exam, setup, client, role):
    headers = setup["headers"][role]
    for patient_id in (setup["patient"], setup["other"]):
        base = url(setup, patient_id=patient_id)
        path = f"{base}/{exam['id']}"
        assert client.get(path, headers=headers).status_code == 404
        assert client.put(path, json={**chart(), "base_revision": 1}, headers=headers).status_code == 404
        assert client.post(f"{path}/finalize", json={"base_revision": 1}, headers=headers).status_code == 404
        assert client.post(f"{path}/void", json={"reason": "x"}, headers=headers).status_code == 404
        assert client.get(f"{path}/revisions", headers=headers).status_code == 404
    assert client.get(url(setup), headers=headers).status_code == 404
    assert client.post(url(setup), json=chart(), headers=headers).status_code == 404


@pytest.mark.isolation
def test_other_clinic_lists_only_its_own_exams(exam, setup, client):
    response = client.get(url(setup, patient_id=setup["other"]), headers=setup["headers"]["other"])
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.rbac
def test_reception_has_no_access(exam, setup, client):
    headers = setup["headers"]["receptionist"]
    path = url(setup, f"/{exam['id']}")
    assert client.get(url(setup), headers=headers).status_code == 403
    assert client.post(url(setup), json=chart(), headers=headers).status_code == 403
    assert client.get(path, headers=headers).status_code == 403
    assert client.put(path, json={**chart(), "base_revision": 1}, headers=headers).status_code == 403
    assert client.post(f"{path}/finalize", json={"base_revision": 1}, headers=headers).status_code == 403
    assert client.post(f"{path}/void", json={"reason": "x"}, headers=headers).status_code == 403
    assert client.get(f"{path}/revisions", headers=headers).status_code == 403


@pytest.mark.rbac
def test_without_session_is_401(setup, client):
    assert client.get(url(setup)).status_code == 401


# --- Historial cronológico (ODON-194) ------------------------------------------


def timeline_events(client, setup, **params):
    response = client.get(f"/patients/{setup['patient']}/timeline", params=params, headers=setup["headers"]["author"])
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_drafts_do_not_appear_in_the_timeline(exam, setup, client):
    assert timeline_events(client, setup, types=["periodontal"]) == []


def test_finalized_and_voided_exams_appear_in_the_timeline(exam, setup, client):
    path = url(setup, f"/{exam['id']}")
    assert client.post(f"{path}/finalize", json={"base_revision": 1}, headers=setup["headers"]["author"]).status_code == 200
    events = timeline_events(client, setup, types=["periodontal"])
    assert [event["action"] for event in events] == ["finalized"]
    assert events[0]["title"] == f"Periodontograma del {YESTERDAY.strftime('%d/%m/%Y')}"
    assert events[0]["detail"] == "Sondaje medio 3,2 mm · sangrado 40 %"
    assert events[0]["ref_id"] == exam["id"]
    assert events[0]["voided"] is False

    assert client.post(f"{path}/void", json={"reason": "Paciente equivocado"},
                       headers=setup["headers"]["author"]).status_code == 200
    events = timeline_events(client, setup, types=["periodontal"])
    assert [event["action"] for event in events] == ["voided", "finalized"]
    assert events[0]["detail"] == "Motivo: Paciente equivocado"
    assert events[1]["voided"] is True
    # Sin filtro también aparecen junto al resto del expediente.
    assert any(event["type"] == "periodontal" for event in timeline_events(client, setup))


def test_a_voided_draft_does_not_appear_in_the_timeline(exam, setup, client):
    assert client.post(url(setup, f"/{exam['id']}/void"), json={"reason": "Duplicado"},
                       headers=setup["headers"]["author"]).status_code == 200
    assert timeline_events(client, setup, types=["periodontal"]) == []


def test_finalized_exam_without_measures_has_no_detail(setup, client, db):
    body = create(client, setup, teeth=[{"tooth": 11, "sites": {"b": {"probing_depth": 2}}}]).json()
    assert client.post(url(setup, f"/{body['id']}/finalize"), json={"base_revision": 1},
                       headers=setup["headers"]["author"]).status_code == 200
    # Se vacía a mano el único sondaje para probar el caso sin promedio.
    db.execute(text("UPDATE periodontal_sites SET probing_depth = NULL WHERE exam_id = :id"), {"id": body["id"]})
    db.commit()
    events = timeline_events(client, setup, types=["periodontal"])
    assert events[0]["detail"] is None


def test_timeline_pages_cross_periodontal_and_other_events(exam, setup, client):
    path = url(setup, f"/{exam['id']}")
    client.post(f"{path}/finalize", json={"base_revision": 1}, headers=setup["headers"]["author"])
    client.post(f"{path}/void", json={"reason": "x"}, headers=setup["headers"]["author"])
    seen, cursor = [], None
    while True:
        params = {"limit": 1, **({"cursor": cursor} if cursor else {})}
        page = client.get(f"/patients/{setup['patient']}/timeline", params=params,
                          headers=setup["headers"]["author"]).json()
        seen += [event["id"] for event in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen))
    assert {f"periodontal.finalized:{exam['id']}", f"periodontal.voided:{exam['id']}"} <= set(seen)
    assert any(event_id.startswith("visit.") for event_id in seen)


# --- Exportación (ODON-198) -----------------------------------------------------


def finalize(client, setup, exam_id):
    response = client.post(url(setup, f"/{exam_id}/finalize"), json={"base_revision": 1},
                           headers=setup["headers"]["author"])
    assert response.status_code == 200, response.text


def test_finalized_exam_exports_a_private_pdf(exam, setup, client, caplog):
    finalize(client, setup, exam["id"])
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        response = client.get(url(setup, f"/{exam['id']}/report.pdf"), headers=setup["headers"]["colleague"])
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["cache-control"] == "private, no-store"
    disposition = response.headers["content-disposition"]
    assert disposition == f'attachment; filename="periodontograma-{YESTERDAY.isoformat()}-{exam["id"]}.pdf"'
    assert "Ríos" not in disposition and "Ana" not in disposition
    # Formato de audit_service.record (ODON-222): <acción> <entidad>_id=<id> ...
    assert f"periodontal_exam.exported periodontal_exam_id={exam['id']} " in caplog.text
    assert "Ríos" not in caplog.text


def test_report_contains_identification_measures_and_no_diagnosis(exam, setup, client):
    finalize(client, setup, exam["id"])
    content = client.get(url(setup, f"/{exam['id']}/report.pdf"), headers=setup["headers"]["author"]).content
    text_content = _pdf_text(content)
    for expected in ("Periodontograma", "Clinica Perio", "Ana R", YESTERDAY.strftime("%d/%m/%Y"),
                     "Sondaje medio", "3,2 mm", "Arcada superior", "Arcada inferior", "no constituye diagn"):
        assert expected in text_content, expected


def test_drafts_and_voided_exams_are_not_exported(exam, setup, client):
    path = url(setup, f"/{exam['id']}/report.pdf")
    response = client.get(path, headers=setup["headers"]["author"])
    assert response.status_code == 409
    assert "Finaliza" in response.json()["detail"]
    finalize(client, setup, exam["id"])
    client.post(url(setup, f"/{exam['id']}/void"), json={"reason": "x"}, headers=setup["headers"]["author"])
    response = client.get(path, headers=setup["headers"]["author"])
    assert response.status_code == 409
    assert "anulado" in response.json()["detail"]


@pytest.mark.isolation
def test_export_is_isolated_by_clinic(exam, setup, client):
    finalize(client, setup, exam["id"])
    for role in ("other", "other_admin"):
        for patient_id in (setup["patient"], setup["other"]):
            path = url(setup, f"/{exam['id']}/report.pdf", patient_id=patient_id)
            assert client.get(path, headers=setup["headers"][role]).status_code == 404


@pytest.mark.rbac
def test_reception_cannot_export(exam, setup, client):
    finalize(client, setup, exam["id"])
    assert client.get(url(setup, f"/{exam['id']}/report.pdf"),
                      headers=setup["headers"]["receptionist"]).status_code == 403


def _pdf_text(content: bytes) -> str:
    """Texto de los streams del PDF (reportlab los comprime con zlib)."""
    import base64
    import re
    import zlib

    chunks = []
    for match in re.finditer(rb"stream\r?\n(.*?)\s*endstream", content, re.S):
        raw = match.group(1).strip()
        if raw.endswith(b"~>"):  # ASCII85 (filtro por defecto de reportlab)
            raw = base64.a85decode(raw, adobe=True)
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        chunks.append(raw.decode("latin-1"))
    return "\n".join(chunks)


def test_download_name_is_readable_across_origins(exam, setup, client):
    """CORS expone Content-Disposition para que el navegador use el nombre del archivo."""
    finalize(client, setup, exam["id"])
    headers = {**setup["headers"]["author"], "Origin": "http://localhost:5173"}
    response = client.get(url(setup, f"/{exam['id']}/report.pdf"), headers=headers)
    assert "content-disposition" in response.headers.get("access-control-expose-headers", "").lower()


def test_admin_of_the_clinic_exports(exam, setup, client):
    finalize(client, setup, exam["id"])
    response = client.get(url(setup, f"/{exam['id']}/report.pdf"), headers=setup["headers"]["admin"])
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_report_survives_unusual_and_long_text(setup, client, db):
    """Caracteres fuera de WinAnsi, saltos de línea y textos largos no rompen el PDF ni se pierden."""
    patient = db.get(Patient, setup["patient"])
    patient.first_name = "Łukasz Nguyễn " + "M" * 90
    db.commit()
    long_note = "Primera línea\nSegunda línea con emoji 😀\t" + "texto largo " * 300
    body = create(client, setup, notes=long_note,
                  teeth=[{"tooth": 11, "note": "Nota de pieza " + "x" * 480, "sites": {"b": {"probing_depth": 3}}}]).json()
    finalize(client, setup, body["id"])
    response = client.get(url(setup, f"/{body['id']}/report.pdf"), headers=setup["headers"]["author"])
    assert response.status_code == 200
    content = _pdf_text(response.content)
    # «ễ» se reduce a «e»; «Ł» no tiene letra base y queda como «?» (nunca un cuadrado).
    assert "?ukasz Nguyen" in content
    assert "Segunda l" in content  # el salto de línea separa líneas, no se dibuja
    assert content.count("largo") >= 300  # la nota sale completa, en varias líneas
    assert "(continuaci" in content
    assert "Notas por pieza" in content


def test_palatal_furcations_follow_the_site_order():
    """En los cuadrantes 1 y 4 lo distal queda a la izquierda, también en la furcación."""
    from app.services.periodontal_report import display_entrances, display_sites

    assert display_sites(16, "lingual") == ["dl", "l", "ml"]
    assert display_entrances(16, "lingual") == ["dp", "mp"]
    assert display_entrances(26, "lingual") == ["mp", "dp"]
    assert display_entrances(46, "buccal") == ["b"]
    assert display_entrances(15, "lingual") == []


# --- Valores predeterminados (ODON-262) ------------------------------------------


def healthy_teeth(numbers=(11, 12), pd=2, gm=0):
    return [
        {"tooth": n, "mobility": 0, "source": "default",
         "sites": {s: {"probing_depth": pd, "gingival_margin": gm, "source": "default"} for s in SITES}}
        for n in numbers
    ]


def test_default_values_are_stored_and_counted_apart(setup, client, db):
    teeth = healthy_teeth()
    teeth[0]["sites"]["mb"] = {"probing_depth": 5, "gingival_margin": -1, "bleeding": True}  # medido
    body = create(client, setup, teeth=teeth).json()
    t11 = tooth(body, 11)
    assert t11["sites"]["mb"]["source"] == "manual"
    assert t11["sites"]["b"]["source"] == "default"
    assert t11["source"] == "default"
    assert body["summary"]["measured_sites"] == 12
    assert body["summary"]["default_sites"] == 11
    sources = {row.source for row in db.query(PeriodontalSite).filter_by(exam_id=body["id"], tooth=12)}
    assert sources == {"default"}


def test_an_empty_site_never_keeps_a_default_source(setup, client, db):
    body = create(client, setup, teeth=[{"tooth": 11, "sites": {"b": {"source": "default"}}}]).json()
    assert tooth(body, 11)["sites"]["b"]["source"] == "manual"


def test_tooth_source_is_manual_without_mobility(setup, client):
    body = create(client, setup, teeth=[{"tooth": 11, "source": "default"}]).json()
    assert tooth(body, 11)["source"] == "manual"


@pytest.mark.parametrize("source", ["ai", "auto", ""])
def test_unknown_source_is_rejected(setup, client, source):
    teeth = [{"tooth": 11, "sites": {"b": {"probing_depth": 2, "source": source}}}]
    assert create(client, setup, teeth=teeth).status_code == 422


def test_editing_a_default_value_is_saved_as_manual(setup, client):
    exam = create(client, setup, teeth=healthy_teeth((11,))).json()
    teeth = healthy_teeth((11,))
    teeth[0]["sites"]["b"] = {"probing_depth": 4, "gingival_margin": 0, "source": "manual"}
    body = save(client, setup, exam, teeth=teeth).json()
    assert tooth(body, 11)["sites"]["b"]["source"] == "manual"
    assert body["summary"]["default_sites"] == 5


def test_revision_snapshot_keeps_the_source(setup, client, db):
    exam = create(client, setup, teeth=healthy_teeth((11,))).json()
    revision = db.query(PeriodontalExamRevision).filter_by(exam_id=exam["id"]).one()
    t11 = next(t for t in revision.data["teeth"] if t["tooth"] == 11)
    assert t11["sites"]["b"]["source"] == "default"


def test_report_counts_default_values(setup, client):
    exam = create(client, setup, teeth=healthy_teeth((11, 21))).json()
    finalize(client, setup, exam["id"])
    content = _pdf_text(client.get(url(setup, f"/{exam['id']}/report.pdf"), headers=setup["headers"]["author"]).content)
    assert "Predeterminados" in content
    assert "valor predeterminado no editado" in content


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE periodontal_sites SET source = 'default' WHERE exam_id = :id AND tooth = 11 AND site = 'dl'",
        "UPDATE periodontal_teeth SET source = 'default', mobility = NULL WHERE exam_id = :id AND tooth = 11",
    ],
)
def test_database_rejects_default_source_without_values(setup, client, db, sql):
    exam = create(client, setup).json()
    with pytest.raises(IntegrityError):
        db.execute(text(sql), {"id": exam["id"]})
        db.commit()
    db.rollback()


def test_deep_default_value_is_never_printed_as_measured(setup, client):
    """Un sondaje profundo copiado y sin editar sale en cursiva (BoldOblique), no como medido."""
    teeth = [{"tooth": 16, "sites": {"mb": {"probing_depth": 6, "gingival_margin": -1, "source": "default"}}}]
    exam = create(client, setup, teeth=teeth).json()
    finalize(client, setup, exam["id"])
    content = client.get(url(setup, f"/{exam['id']}/report.pdf"), headers=setup["headers"]["author"]).content
    assert b"Helvetica-BoldOblique" in content

