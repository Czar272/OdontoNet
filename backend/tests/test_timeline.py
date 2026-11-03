"""Historial cronológico del paciente (ODON-162)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.security import hash_password
from app.models import Appointment, Patient, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.records]

NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def setup(db, client):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Timeline", "doc@timeline-clinica.com")
    _, _, _ = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-timeline.com")
    reception = User(name="Recepción", email="recepcion@timeline-clinica.com", hashed_password=hash_password(PASSWORD), role="receptionist", clinic_id=clinic.id)
    patient = Patient(first_name="Ana", last_name="Timeline", clinic_id=clinic.id)
    sibling = Patient(first_name="Otro", last_name="Paciente", clinic_id=clinic.id)
    db.add_all([reception, patient, sibling])
    db.commit()

    headers = {
        "doctor": auth_headers(client, "doc@timeline-clinica.com"),
        "receptionist": auth_headers(client, "recepcion@timeline-clinica.com"),
        "other": auth_headers(client, "doc@ajena-timeline.com"),
    }
    h = headers["doctor"]

    def ok(response):
        assert response.status_code in (200, 201), response.text
        return response.json()

    base = f"/patients/{patient.id}"
    # Citas: una atendida, una no asistida y una programada (no aparece).
    for days, status_value, reason in [(40, "completed", "Limpieza"), (35, "no_show", "Control"), (-5, "scheduled", "Futura")]:
        db.add(Appointment(clinic_id=clinic.id, patient_id=patient.id, doctor_id=doctor.id, starts_at=NOW - timedelta(days=days), duration_minutes=30, status=status_value, reason=reason, created_by_user_id=doctor_user.id))
    db.commit()

    ok(client.post(f"{base}/medical-history", json={"allergies": "Penicilina", "base_version": None}, headers=h))
    first = ok(client.post(f"{base}/visits", json={"visit_at": (NOW - timedelta(days=10)).isoformat(), "doctor_id": doctor.id, "reason": "Evaluación", "diagnosis": "Gingivitis"}, headers=h))
    ok(client.put(f"{base}/visits/{first['id']}", json={"visit_at": first["visit_at"], "doctor_id": doctor.id, "reason": "Evaluación", "diagnosis": "Periodontitis estadio I", "base_revision": 1}, headers=h))
    wrong = ok(client.post(f"{base}/visits", json={"visit_at": (NOW - timedelta(days=9)).isoformat(), "doctor_id": doctor.id, "reason": "Duplicada"}, headers=h))
    ok(client.post(f"{base}/visits/{wrong['id']}/void", json={"reason": "Registrada dos veces"}, headers=h))
    treatment = ok(client.post(f"{base}/treatments", json={"procedure": "Raspado", "tooth": 36, "proposed_visit_id": first["id"]}, headers=h))
    ok(client.post(f"{base}/treatments/{treatment['id']}/status", json={"status": "accepted"}, headers=h))
    ok(client.post(f"{base}/treatments/{treatment['id']}/status", json={"status": "completed", "completed_visit_id": first["id"]}, headers=h))
    ok(client.post(f"{base}/medical-history", json={"allergies": "Penicilina y látex", "base_version": 1}, headers=h))
    # Algo del otro paciente: no debe aparecer.
    ok(client.post(f"/patients/{sibling.id}/treatments", json={"procedure": "Ajeno"}, headers=h))

    return {"patient": patient.id, "headers": headers, "visit": first["id"], "treatment": treatment["id"], "doctor": doctor.id}


def timeline(client, setup, role="doctor", **params):
    return client.get(f"/patients/{setup['patient']}/timeline", params=params, headers=setup["headers"][role])


def all_events(client, setup, **params):
    events, cursor = [], None
    while True:
        page = timeline(client, setup, cursor=cursor, **params).json() if cursor else timeline(client, setup, **params).json()
        events += page["items"]
        cursor = page["next_cursor"]
        if not cursor:
            return events


def test_timeline_includes_every_event_type_newest_first(client, setup):
    body = timeline(client, setup).json()

    kinds = [f"{e['type']}.{e['action']}" for e in body["items"]]
    assert sorted(kinds) == sorted([
        "medical_history.version", "medical_history.version",
        "visit.attended", "visit.edited", "visit.attended", "visit.voided",
        "treatment.proposed", "treatment.accepted", "treatment.completed",
        "appointment.completed", "appointment.no_show",
    ])
    dates = [e["occurred_at"] for e in body["items"]]
    assert dates == sorted(dates, reverse=True)
    assert body["next_cursor"] is None


def test_clinical_dates_order_visits_and_appointments(client, setup):
    items = timeline(client, setup).json()["items"]

    # Lo más antiguo: la cita atendida hace 40 días y la no asistida hace 35.
    assert [e["type"] for e in items[-2:]] == ["appointment", "appointment"]
    assert items[-1]["title"] == "Cita atendida: Limpieza"
    assert items[-2]["title"] == "No asistió a la cita: Control"


def test_event_contents(client, setup):
    items = {f"{e['type']}.{e['action']}": e for e in timeline(client, setup).json()["items"]}

    attended = [e for e in timeline(client, setup).json()["items"] if e["action"] == "attended" and e["title"] == "Consulta: Evaluación"][0]
    assert attended["detail"] == "Periodontitis estadio I"
    assert attended["actor"] == {"id": setup["doctor"], "name": "Dr. Clinica Timeline"}
    assert attended["ref_id"] == setup["visit"]
    assert items["visit.edited"]["detail"] == "Revisión 2"
    assert items["visit.edited"]["ref_id"] == setup["visit"]
    assert items["visit.voided"]["detail"] == "Motivo: Registrada dos veces"
    assert items["treatment.completed"]["title"] == "Tratamiento completado: Raspado (pieza 36)"
    assert items["treatment.completed"]["ref_id"] == setup["treatment"]
    histories = [e for e in timeline(client, setup).json()["items"] if e["type"] == "medical_history"]
    assert [h["title"] for h in histories] == ["Historia médica actualizada (versión 2)", "Historia médica registrada"]


def test_voided_visit_is_flagged(client, setup):
    items = timeline(client, setup).json()["items"]

    duplicated = [e for e in items if e["action"] == "attended" and e["title"] == "Consulta: Duplicada"][0]
    assert duplicated["voided"] is True


def test_filter_by_type(client, setup):
    items = timeline(client, setup, types=["treatment", "appointment"]).json()["items"]

    assert {e["type"] for e in items} == {"treatment", "appointment"}
    assert len(items) == 5


def test_pages_of_given_size_without_gaps_or_duplicates(client, setup):
    full = [e["id"] for e in timeline(client, setup).json()["items"]]

    first = timeline(client, setup, limit=4).json()
    assert len(first["items"]) == 4
    assert first["next_cursor"]
    paged = [e["id"] for e in all_events(client, setup, limit=4)]

    assert paged == full
    assert len(set(paged)) == len(paged) == 11


def test_default_page_size_is_20(client, setup, db):
    patient = db.get(Patient, setup["patient"])
    doctor_user = db.query(User).filter(User.email == "doc@timeline-clinica.com").one()
    for i in range(15):
        db.add(Appointment(clinic_id=patient.clinic_id, patient_id=patient.id, doctor_id=setup["doctor"], starts_at=NOW - timedelta(days=100 + i), duration_minutes=30, status="completed", created_by_user_id=doctor_user.id))
    db.commit()

    body = timeline(client, setup).json()

    assert len(body["items"]) == 20
    assert body["next_cursor"]
    assert len(all_events(client, setup)) == 26


def test_invalid_cursor_and_type_are_422(client, setup):
    assert timeline(client, setup, cursor="no-es-un-cursor").status_code == 422
    assert timeline(client, setup, types=["imagen"]).status_code == 422
    assert timeline(client, setup, limit=0).status_code == 422


def test_empty_timeline(client, setup, db):
    patient = db.get(Patient, setup["patient"])
    empty = Patient(first_name="Sin", last_name="Historial", clinic_id=patient.clinic_id)
    db.add(empty)
    db.commit()

    body = client.get(f"/patients/{empty.id}/timeline", headers=setup["headers"]["doctor"]).json()

    assert body == {"items": [], "next_cursor": None}


@pytest.mark.rbac
def test_receptionist_has_no_access(client, setup):
    assert timeline(client, setup, role="receptionist").status_code == 403


@pytest.mark.isolation
def test_other_clinic_gets_404(client, setup):
    response = timeline(client, setup, role="other")

    assert response.status_code == 404
    assert response.json() == {"detail": "Paciente no encontrado."}


@pytest.mark.isolation
def test_other_patients_events_are_not_included(client, setup):
    titles = [e["title"] for e in timeline(client, setup).json()["items"]]

    assert not any("Ajeno" in title for title in titles)
