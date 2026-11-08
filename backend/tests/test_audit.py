"""Auditoría persistente de cambios y exportaciones (ODON-222).

Cubre que cada operación deje exactamente un evento sin valores ni datos
personales, que el evento se revierta con la operación, la integridad de la
cadena de hashes (trigger de solo agregado y detección de alteraciones),
GET /audit (roles, aislamiento, filtros, paginación) y scripts/verify_audit.
"""
import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.auth.security import hash_password
from app.database.connection import engine
from app.main import app
from app.models import AuditEvent, Patient, User
from app.services import audit_service, password_service
from scripts import verify_audit
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.records]

CLINIC_TZ = ZoneInfo("America/Guatemala")
YESTERDAY = date.today() - timedelta(days=1)


@pytest.fixture
def setup(db, client):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Auditoria", "doc@auditoria-clinica.com")
    other_clinic, other_doctor, _ = create_clinic_with_doctor(db, "Clinica Ajena Auditoria", "doc@ajena-auditoria.com")
    admin = User(name="Admin Auditoria", email="admin@auditoria-clinica.com", hashed_password=hash_password(PASSWORD),
                 role="admin", clinic_id=clinic.id)
    colleague = User(name="Dra. Colega", email="colega@auditoria-clinica.com", hashed_password=hash_password(PASSWORD),
                     role="doctor", clinic_id=clinic.id)
    receptionist = User(name="Recepcion Auditoria", email="recepcion@auditoria-clinica.com",
                        hashed_password=hash_password(PASSWORD), role="receptionist", clinic_id=clinic.id)
    other_admin = User(name="Admin Ajena", email="admin@ajena-auditoria.com", hashed_password=hash_password(PASSWORD),
                       role="admin", clinic_id=other_clinic.id)
    db.add_all([admin, colleague, receptionist, other_admin])
    patient = Patient(first_name="Paciente", last_name="Base", clinic_id=clinic.id)
    other_patient = Patient(first_name="Paciente", last_name="Ajeno", clinic_id=other_clinic.id)
    db.add_all([patient, other_patient])
    db.commit()
    return {
        "db": db,
        "clinic": clinic.id,
        "other_clinic": other_clinic.id,
        "doctor": doctor.id,
        "users": {
            "admin": admin.id, "doctor": doctor_user.id, "colleague": colleague.id,
            "receptionist": receptionist.id, "other_admin": other_admin.id, "other_doctor": other_doctor.id,
        },
        "patient": patient.id,
        "other_patient": other_patient.id,
        "headers": {
            "admin": auth_headers(client, "admin@auditoria-clinica.com"),
            "doctor": auth_headers(client, "doc@auditoria-clinica.com"),
            "receptionist": auth_headers(client, "recepcion@auditoria-clinica.com"),
            "other_admin": auth_headers(client, "admin@ajena-auditoria.com"),
        },
    }


def last_id(db) -> int:
    db.expire_all()
    return db.query(AuditEvent.id).order_by(AuditEvent.id.desc()).limit(1).scalar() or 0


def events_since(db, since: int) -> list[AuditEvent]:
    db.expire_all()
    return db.query(AuditEvent).filter(AuditEvent.id > since).order_by(AuditEvent.id).all()


def only_event(db, since: int) -> AuditEvent:
    events = events_since(db, since)
    assert len(events) == 1, [e.action for e in events]
    return events[0]


def row_text(event: AuditEvent) -> str:
    """Todas las columnas de la fila como texto, para buscar valores filtrados."""
    return json.dumps(
        {column.name: getattr(event, column.name) for column in AuditEvent.__table__.columns},
        default=str, ensure_ascii=False,
    )


def assert_no_values(client, setup, event: AuditEvent, *secrets: str) -> None:
    stored = row_text(event)
    listed = client.get("/audit", headers=setup["headers"]["admin"]).text
    for secret in secrets:
        assert secret not in stored, secret
        assert secret not in listed, secret


def tomorrow_at(hour: int) -> str:
    day = datetime.now(CLINIC_TZ).date() + timedelta(days=1)
    return datetime(day.year, day.month, day.day, hour, tzinfo=CLINIC_TZ).isoformat()


def create_appointment(client, setup, hour=10):
    return client.post("/appointments/", json={
        "patient_id": setup["patient"], "doctor_id": setup["doctor"], "starts_at": tomorrow_at(hour),
        "duration_minutes": 30, "reason": "Motivo reservado de la cita", "allow_outside_schedule": True,
    }, headers=setup["headers"]["admin"])


def create_visit(client, setup, role="doctor"):
    response = client.post(f"/patients/{setup['patient']}/visits", json={
        "visit_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "doctor_id": setup["doctor"], "reason": "Motivo clínico reservado",
    }, headers=setup["headers"][role])
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_patient(client, setup, role="admin", **overrides):
    body = {"first_name": "Zacarias", "last_name": "Quintanilla", "email": "zq@privado-mail.com",
            "phone": "5550-1234", **overrides}
    response = client.post("/patients/", json=body, headers=setup["headers"][role])
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- Eventos registrados --------------------------------------------------------


@pytest.mark.patients
def test_patient_create_and_update_are_recorded_without_values(client, setup):
    db = setup["db"]
    before = last_id(db)
    patient_id = create_patient(client, setup)

    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.patient_id) == (
        "patient.created", "patient", patient_id, patient_id)
    assert (event.actor_user_id, event.actor_role, event.clinic_id) == (
        setup["users"]["admin"], "admin", setup["clinic"])
    assert event.fields is None

    before = last_id(db)
    response = client.patch(f"/patients/{patient_id}", json={"phone": "5550-9876", "email": "nuevo@privado-mail.com"},
                            headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_id, event.patient_id) == ("patient.updated", patient_id, patient_id)
    assert event.fields == ["email", "phone"]
    assert_no_values(client, setup, event, "Zacarias", "Quintanilla", "zq@privado-mail.com", "5550-1234",
                     "5550-9876", "nuevo@privado-mail.com")


@pytest.mark.patients
def test_patient_without_changes_records_nothing(client, setup):
    db = setup["db"]
    before = last_id(db)
    response = client.patch(f"/patients/{setup['patient']}", json={"first_name": "Paciente"},
                            headers=setup["headers"]["admin"])
    assert response.status_code == 200
    assert events_since(db, before) == []


@pytest.mark.patients
def test_patient_doctor_change_also_records_doctor_changed(client, setup):
    db = setup["db"]
    before = last_id(db)
    response = client.patch(f"/patients/{setup['patient']}", json={"doctor_id": setup["doctor"]},
                            headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    events = events_since(db, before)
    assert [(e.action, e.fields) for e in events] == [
        ("patient.updated", ["doctor_id"]), ("patient.doctor_changed", ["doctor_id"])]


@pytest.mark.patients
def test_patient_archive_and_reactivate_are_recorded(client, setup):
    db = setup["db"]
    before = last_id(db)
    path = f"/patients/{setup['patient']}"
    assert client.post(f"{path}/archive", headers=setup["headers"]["admin"]).status_code == 200
    assert client.post(f"{path}/archive", headers=setup["headers"]["admin"]).status_code == 200  # idempotente
    assert client.post(f"{path}/reactivate", headers=setup["headers"]["admin"]).status_code == 200
    events = events_since(db, before)
    assert [e.action for e in events] == ["patient.archived", "patient.reactivated"]
    assert all(e.patient_id == setup["patient"] and e.fields == ["archived_at"] for e in events)


@pytest.mark.appointments
def test_appointment_create_and_status_change_are_recorded(client, setup):
    db = setup["db"]
    before = last_id(db)
    response = create_appointment(client, setup)
    assert response.status_code == 201, response.text
    appointment_id = response.json()["id"]
    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.patient_id, event.actor_user_id) == (
        "appointment.created", "appointment", appointment_id, setup["patient"], setup["users"]["admin"])

    before = last_id(db)
    response = client.post(f"/appointments/{appointment_id}/status",
                           json={"status": "confirmed", "note": "Confirmó por teléfono 5550-4444"},
                           headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_id, event.patient_id, event.fields) == (
        "appointment.status_changed", appointment_id, setup["patient"], ["status"])
    assert_no_values(client, setup, event, "Motivo reservado", "5550-4444", "Confirmó")


def test_clinical_visit_void_is_recorded_without_reason(client, setup):
    db = setup["db"]
    visit_id = create_visit(client, setup)
    before = last_id(db)
    response = client.post(f"/patients/{setup['patient']}/visits/{visit_id}/void",
                           json={"reason": "Registrada en el expediente equivocado"},
                           headers=setup["headers"]["doctor"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.patient_id, event.actor_user_id) == (
        "clinical_visit.voided", "clinical_visit", visit_id, setup["patient"], setup["users"]["doctor"])
    assert event.fields == ["void_reason", "voided_at"]
    assert_no_values(client, setup, event, "expediente equivocado", "Motivo clínico reservado")


@pytest.mark.periodontal
def test_periodontal_finalize_and_export_are_recorded(client, setup):
    db = setup["db"]
    base = f"/patients/{setup['patient']}/periodontal-exams"
    response = client.post(base, json={
        "exam_date": YESTERDAY.isoformat(), "notes": "Nota periodontal reservada",
        "teeth": [{"tooth": 16, "sites": {"b": {"probing_depth": 3, "gingival_margin": 0}}}],
    }, headers=setup["headers"]["doctor"])
    assert response.status_code == 201, response.text
    exam_id = response.json()["id"]

    before = last_id(db)
    response = client.post(f"{base}/{exam_id}/finalize", json={"base_revision": 1},
                           headers=setup["headers"]["doctor"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.patient_id, event.fields) == (
        "periodontal_exam.finalized", "periodontal_exam", exam_id, setup["patient"], ["status"])

    before = last_id(db)
    response = client.get(f"{base}/{exam_id}/report.pdf", headers=setup["headers"]["doctor"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_id, event.patient_id) == (
        "periodontal_exam.exported", exam_id, setup["patient"])
    assert_no_values(client, setup, event, "Nota periodontal reservada")


@pytest.mark.dashboard
def test_report_csv_export_is_recorded(client, setup):
    db = setup["db"]
    before = last_id(db)
    response = client.get("/reports/appointments.csv", headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.patient_id, event.fields) == (
        "report.exported", "report", None, None, ["appointments"])
    assert event.actor_user_id == setup["users"]["admin"]


@pytest.mark.users
def test_user_update_with_password_records_field_names_only(client, setup):
    db = setup["db"]
    before = last_id(db)
    secret = "Clave-Muy-Secreta-987"
    response = client.patch(f"/users/{setup['users']['colleague']}", json={
        "name": "Nombre Nuevo Reservado", "email": "correo.nuevo@reservado-mail.com", "password": secret,
    }, headers=setup["headers"]["admin"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.actor_user_id, event.patient_id) == (
        "user.updated", "user", setup["users"]["colleague"], setup["users"]["admin"], None)
    assert event.fields == ["email", "name", "password"]
    assert_no_values(client, setup, event, secret, "Nombre Nuevo Reservado", "correo.nuevo@reservado-mail.com")


@pytest.mark.users
def test_user_create_deactivate_and_reactivate_are_recorded(client, setup):
    db = setup["db"]
    before = last_id(db)
    response = client.post("/users/", json={
        "name": "Usuario Reservado", "email": "usuario@reservado-mail.com", "password": "Otra-Clave-Reservada-1",
        "role": "receptionist",
    }, headers=setup["headers"]["admin"])
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    assert client.post(f"/users/{user_id}/deactivate", headers=setup["headers"]["admin"]).status_code == 200
    assert client.post(f"/users/{user_id}/activate", headers=setup["headers"]["admin"]).status_code == 200
    events = events_since(db, before)
    assert [(e.action, e.entity_id, e.fields) for e in events] == [
        ("user.created", user_id, None),
        ("user.deactivated", user_id, ["is_active"]),
        ("user.reactivated", user_id, ["is_active"]),
    ]
    for event in events:
        assert_no_values(client, setup, event,
                         "Usuario Reservado", "usuario@reservado-mail.com", "Otra-Clave-Reservada-1")


@pytest.mark.auth
def test_password_change_is_recorded_without_password(client, setup):
    db = setup["db"]
    before = last_id(db)
    new_password = "Nueva-Clave-Segura-456"
    response = client.post("/auth/change-password", json={
        "current_password": PASSWORD, "new_password": new_password,
    }, headers=setup["headers"]["doctor"])
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_type, event.entity_id, event.actor_user_id, event.clinic_id, event.fields) == (
        "auth.password_changed", "user", setup["users"]["doctor"], setup["users"]["doctor"], setup["clinic"],
        ["password"])
    assert_no_values(client, setup, event, new_password, PASSWORD)


@pytest.mark.auth
def test_password_reset_confirm_is_recorded_for_the_user(client, setup):
    db = setup["db"]
    _, link = password_service.request_reset(db, "colega@auditoria-clinica.com")
    token = link.split("token=")[1]
    before = last_id(db)
    new_password = "Clave-Restablecida-789"
    response = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": new_password})
    assert response.status_code == 200, response.text
    event = only_event(db, before)
    assert (event.action, event.entity_id, event.actor_user_id, event.clinic_id, event.fields) == (
        "auth.password_reset_completed", setup["users"]["colleague"], setup["users"]["colleague"],
        setup["clinic"], ["password"])
    assert_no_values(client, setup, event, new_password, token)


@pytest.mark.users
def test_clinic_and_doctor_profile_changes_are_recorded(client, setup):
    db = setup["db"]
    before = last_id(db)
    assert client.patch("/clinic", json={"phone": "2222-3333"}, headers=setup["headers"]["admin"]).status_code == 200
    assert client.patch(f"/doctors/{setup['doctor']}", json={"license_number": "COL-12345"},
                        headers=setup["headers"]["admin"]).status_code == 200
    response = client.post("/doctors/", json={"user_id": setup["users"]["colleague"]},
                           headers=setup["headers"]["admin"])
    assert response.status_code == 201, response.text
    events = events_since(db, before)
    assert [(e.action, e.entity_type, e.entity_id, e.fields) for e in events] == [
        ("clinic.updated", "clinic", setup["clinic"], ["phone"]),
        ("doctor.updated", "doctor", setup["doctor"], ["license_number"]),
        ("doctor.created", "doctor", response.json()["id"], None),
    ]
    assert not any("2222-3333" in row_text(e) or "COL-12345" in row_text(e) for e in events)


# --- Reversión ------------------------------------------------------------------


@pytest.mark.appointments
def test_failed_operation_leaves_no_event(client, setup):
    db = setup["db"]
    assert create_appointment(client, setup).status_code == 201
    before = last_id(db)
    response = create_appointment(client, setup)  # mismo horario: choca con la anterior
    assert response.status_code == 409, response.text
    assert events_since(db, before) == []


@pytest.mark.patients
def test_event_is_rolled_back_with_the_operation(client, setup, monkeypatch):
    """Si algo falla después de registrar el evento, ni el cambio ni el evento quedan."""
    db = setup["db"]
    original = audit_service.record

    def record_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("falla simulada después de auditar")

    monkeypatch.setattr(audit_service, "record", record_then_fail)
    before = last_id(db)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/patients/", json={"first_name": "Revertido", "last_name": "Prueba"}, headers=setup["headers"]["admin"])
    assert response.status_code == 500
    assert events_since(db, before) == []
    assert db.query(Patient).filter(Patient.first_name == "Revertido").count() == 0


# --- Integridad -----------------------------------------------------------------


def make_events(client, setup, count=3):
    for index in range(count):
        create_patient(client, setup, first_name=f"Cadena{index}", email=f"cadena{index}@privado-mail.com")


def test_chain_is_valid_after_several_events(client, setup):
    make_events(client, setup)
    create_visit(client, setup)
    db = setup["db"]
    db.expire_all()
    assert db.query(AuditEvent).filter(AuditEvent.clinic_id == setup["clinic"]).count() == 4
    assert audit_service.verify_chain(db, setup["clinic"]) == []


def test_update_is_rejected_by_trigger(client, setup):
    make_events(client, setup, 1)
    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text("UPDATE audit_events SET hash = repeat('0', 64)"))


def test_delete_without_purge_setting_is_rejected(client, setup):
    make_events(client, setup, 1)
    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM audit_events"))
    assert last_id(setup["db"]) > 0


def tamper(event_id: int) -> None:
    """Altera una fila saltándose el trigger (session_replication_role requiere superusuario)."""
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        conn.execute(text("UPDATE audit_events SET action = 'patient.alterado' WHERE id = :id"), {"id": event_id})


def test_direct_tampering_is_detected(client, setup):
    make_events(client, setup)
    db = setup["db"]
    middle = db.query(AuditEvent.id).order_by(AuditEvent.id).offset(1).limit(1).scalar()
    tamper(middle)
    db.expire_all()
    problems = audit_service.verify_chain(db, setup["clinic"])
    assert problems == [f"evento {middle}: el contenido no coincide con su hash"]


# --- GET /audit -----------------------------------------------------------------


@pytest.fixture
def mixed_events(client, setup):
    """Eventos de administración y del doctor en la clínica, y uno de la clínica ajena."""
    patient_id = create_patient(client, setup)                      # admin
    visit_id = create_visit(client, setup)                          # doctor
    client.patch(f"/patients/{patient_id}", json={"phone": "5550-0000"}, headers=setup["headers"]["admin"])
    other = client.post("/patients/", json={"first_name": "Ajeno", "last_name": "Otro"},
                        headers=setup["headers"]["other_admin"])
    assert other.status_code == 201
    return {"patient": patient_id, "visit": visit_id, "other_patient": other.json()["id"]}


def audit(client, setup, role="admin", **params):
    return client.get("/audit", params=params, headers=setup["headers"][role])


@pytest.mark.isolation
def test_admin_sees_all_events_of_own_clinic_only(client, setup, mixed_events):
    response = audit(client, setup)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [i["action"] for i in items] == ["patient.updated", "clinical_visit.created", "patient.created"]
    assert {i["actor"]["id"] for i in items} == {setup["users"]["admin"], setup["users"]["doctor"]}
    assert mixed_events["other_patient"] not in {i["patient_id"] for i in items}
    assert items[0]["fields"] == ["phone"]
    assert items[0]["actor"] == {"id": setup["users"]["admin"], "name": "Admin Auditoria", "role": "admin"}

    other = audit(client, setup, role="other_admin").json()["items"]
    assert [(i["action"], i["patient_id"]) for i in other] == [("patient.created", mixed_events["other_patient"])]


@pytest.mark.rbac
def test_doctor_sees_only_own_events(client, setup, mixed_events):
    for params in ({}, {"actor_user_id": setup["users"]["admin"]}):
        items = audit(client, setup, role="doctor", **params).json()["items"]
        assert [(i["action"], i["actor"]["id"]) for i in items] == [
            ("clinical_visit.created", setup["users"]["doctor"])]


@pytest.mark.rbac
def test_admin_can_filter_by_actor(client, setup, mixed_events):
    items = audit(client, setup, actor_user_id=setup["users"]["doctor"]).json()["items"]
    assert [i["action"] for i in items] == ["clinical_visit.created"]


@pytest.mark.rbac
def test_receptionist_and_anonymous_cannot_read_audit(client, setup):
    assert audit(client, setup, role="receptionist").status_code == 403
    assert client.get("/audit").status_code == 401


@pytest.mark.rbac
@pytest.mark.isolation
def test_other_clinic_ids_in_filters_return_nothing(client, setup, mixed_events):
    items = audit(client, setup, patient_id=mixed_events["other_patient"]).json()["items"]
    assert items == []
    items = audit(client, setup, actor_user_id=setup["users"]["other_admin"]).json()["items"]
    assert items == []


def test_filters(client, setup, mixed_events):
    def actions(**params):
        response = audit(client, setup, **params)
        assert response.status_code == 200, response.text
        return [i["action"] for i in response.json()["items"]]

    assert actions(action="patient.created") == ["patient.created"]
    assert actions(entity_type="clinical_visit") == ["clinical_visit.created"]
    assert actions(entity_type="patient") == ["patient.updated", "patient.created"]
    assert actions(patient_id=setup["patient"]) == ["clinical_visit.created"]
    assert actions(patient_id=mixed_events["patient"]) == ["patient.updated", "patient.created"]

    today = datetime.now(CLINIC_TZ).date()
    assert len(actions(**{"from": today.isoformat(), "to": today.isoformat()})) == 3
    assert actions(**{"from": (today + timedelta(days=1)).isoformat()}) == []
    assert actions(to=(today - timedelta(days=1)).isoformat()) == []


def test_cursor_paginates_without_duplicates_or_gaps(client, setup, mixed_events):
    make_events(client, setup, 2)
    expected = [i["id"] for i in audit(client, setup).json()["items"]]
    assert len(expected) == 5

    seen, cursor = [], None
    for _ in range(10):
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = audit(client, setup, **params).json()
        assert len(page["items"]) <= 2
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == expected


def test_invalid_cursor_is_422(client, setup):
    response = audit(client, setup, cursor="abc")
    assert response.status_code == 422
    assert response.json()["detail"] == "Cursor inválido."


# --- Script de verificación -----------------------------------------------------


def test_verify_script_reports_tampering(client, setup, capsys):
    make_events(client, setup)
    assert verify_audit.main() == 0
    assert "cadena íntegra" in capsys.readouterr().out

    first = setup["db"].query(AuditEvent.id).order_by(AuditEvent.id).limit(1).scalar()
    tamper(first)
    assert verify_audit.main() == 1
    assert f"evento {first}" in capsys.readouterr().out


# --- Ajustes de la revisión independiente ---------------------------------------

def test_concurrent_events_keep_a_single_chain(setup):
    """Escrituras simultáneas en la misma clínica no bifurcan la cadena (bloqueo por clínica)."""
    import threading

    from app.database.connection import SessionLocal

    errors = []

    def write(index: int) -> None:
        try:
            with SessionLocal() as session:
                actor = session.get(User, setup["users"]["admin"])
                audit_service.record(session, actor, "clinic.updated", "clinic", setup["clinic"], fields=[f"f{index}"])
                session.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    with SessionLocal() as session:
        assert session.query(AuditEvent).filter(AuditEvent.clinic_id == setup["clinic"]).count() == 8
        assert audit_service.verify_chain(session, setup["clinic"]) == []


def test_extreme_end_date_is_rejected(client, setup):
    response = client.get("/audit", params={"to": "9999-12-31"}, headers=setup["headers"]["admin"])
    assert response.status_code == 422
