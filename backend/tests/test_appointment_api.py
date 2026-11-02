"""CRUD de citas, validación de cruces y concurrencia (ODON-134 / ODON-135 a 137)."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import appointment_routes
from app.auth.security import hash_password
from app.main import app
from app.models import Appointment, Doctor, Patient, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.appointments]

ROLES = ("admin", "doctor", "receptionist")
GT = timezone(timedelta(hours=-6))


def tomorrow_at(hour: int, minute: int = 0) -> datetime:
    """Una hora fija de pasado mañana en Guatemala: siempre en el futuro."""
    day = (datetime.now(GT) + timedelta(days=2)).date()
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=GT)


NINE = tomorrow_at(9)


def iso(value: datetime) -> str:
    return value.isoformat()


@pytest.fixture
def agenda(db, client):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Citas", "doc@citas-clinica.com")
    other_clinic, _, foreign_doctor = create_clinic_with_doctor(db, "Clinica Lejana Citas", "doc@lejana-citas.com")

    second_user = User(name="Dra. Segunda", email="segunda@citas-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id)
    retired_user = User(name="Dr. Retirado", email="retirado@citas-clinica.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=clinic.id, is_active=False)
    db.add_all([second_user, retired_user])
    for role in ("admin", "receptionist"):
        db.add(User(name=role, email=f"{role}@citas-clinica.com", hashed_password=hash_password(PASSWORD), role=role, clinic_id=clinic.id))
    db.flush()
    second = Doctor(user_id=second_user.id, clinic_id=clinic.id)
    retired = Doctor(user_id=retired_user.id, clinic_id=clinic.id)
    patients = [Patient(first_name=f"Paciente{i}", last_name="Agenda", phone="5555-0000", clinic_id=clinic.id) for i in range(6)]
    archived = Patient(first_name="Archivada", last_name="Agenda", clinic_id=clinic.id, archived_at=datetime.now(timezone.utc))
    foreign_patient = Patient(first_name="Ajena", last_name="Agenda", clinic_id=other_clinic.id)
    db.add_all([second, retired, *patients, archived, foreign_patient])
    db.commit()

    return {
        "clinic": clinic.id, "doctor": doctor.id, "second": second.id, "retired": retired.id,
        "foreign_doctor": foreign_doctor.id, "patients": [p.id for p in patients],
        "patient": patients[0].id, "archived": archived.id, "foreign_patient": foreign_patient.id,
        "doctor_user": doctor_user.id,
        "headers": {
            "admin": auth_headers(client, "admin@citas-clinica.com"),
            "doctor": auth_headers(client, "doc@citas-clinica.com"),
            "receptionist": auth_headers(client, "receptionist@citas-clinica.com"),
            "other": auth_headers(client, "doc@lejana-citas.com"),
        },
    }


def payload(agenda, starts_at=NINE, **overrides):
    data = {"patient_id": agenda["patient"], "doctor_id": agenda["doctor"], "starts_at": iso(starts_at), "duration_minutes": 30}
    data.update(overrides)
    return data


def create(client, agenda, role="receptionist", **kwargs):
    return client.post("/appointments/", json=payload(agenda, **kwargs), headers=agenda["headers"][role])


def created_id(client, agenda, **kwargs) -> int:
    response = create(client, agenda, **kwargs)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def set_status(db, appointment_id, status):
    appointment = db.get(Appointment, appointment_id)
    appointment.status = status
    db.commit()


def listing(client, agenda, role="receptionist", **params):
    return client.get("/appointments/", params=params, headers=agenda["headers"][role])


def day_range():
    start = NINE.replace(hour=0)
    return {"start": iso(start), "end": iso(start + timedelta(days=1))}


# --- Alta (ODON-135) -----------------------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_schedule(client, agenda, role):
    response = create(client, agenda, role, reason="Limpieza")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["duration_minutes"] == 30
    assert datetime.fromisoformat(body["ends_at"]) == NINE + timedelta(minutes=30)
    assert body["reason"] == "Limpieza"
    assert body["patient"] == {"id": agenda["patient"], "first_name": "Paciente0", "last_name": "Agenda", "archived_at": None}
    assert body["doctor"]["id"] == agenda["doctor"]
    assert body["clinic_id"] == agenda["clinic"]


def test_clinic_status_and_author_come_from_the_session(client, agenda, db):
    response = create(client, agenda, "doctor", clinic_id=999, status="completed", created_by_user_id=1)

    assert response.status_code == 201
    stored = db.get(Appointment, response.json()["id"])
    assert stored.clinic_id == agenda["clinic"]
    assert stored.status == "scheduled"
    assert stored.created_by_user_id == agenda["doctor_user"]


def test_duration_defaults_to_30_minutes(client, agenda):
    data = payload(agenda)
    del data["duration_minutes"]

    response = client.post("/appointments/", json=data, headers=agenda["headers"]["admin"])

    assert response.json()["duration_minutes"] == 30


@pytest.mark.parametrize(
    ("overrides", "status", "detail"),
    [
        ({"doctor_id": "retired"}, 422, "El doctor seleccionado está inactivo."),
        ({"doctor_id": "foreign_doctor"}, 422, "El doctor seleccionado no pertenece a la clínica."),
        ({"doctor_id": 999999}, 422, "El doctor seleccionado no pertenece a la clínica."),
        ({"patient_id": "foreign_patient"}, 422, "El paciente seleccionado no pertenece a la clínica."),
        ({"patient_id": "archived"}, 409, "El paciente está archivado. Reactívalo para agendarle citas."),
    ],
)
def test_invalid_patient_or_doctor(client, agenda, overrides, status, detail):
    resolved = {key: agenda.get(value, value) if isinstance(value, str) else value for key, value in overrides.items()}

    response = create(client, agenda, **resolved)

    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_cannot_schedule_in_the_past(client, agenda):
    response = create(client, agenda, starts_at=datetime.now(GT).replace(second=0, microsecond=0) - timedelta(minutes=5))

    assert response.status_code == 422
    assert response.json()["detail"] == "La cita no puede empezar en el pasado."


def test_can_schedule_for_the_current_minute(client, agenda):
    response = create(client, agenda, starts_at=datetime.now(GT).replace(second=0, microsecond=0))

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    ("starts_at", "message"),
    [
        (NINE.replace(tzinfo=None).isoformat(), "La fecha y hora deben incluir la zona horaria."),
        (NINE.replace(second=30).isoformat(), "La hora debe ser exacta al minuto."),
    ],
)
def test_ambiguous_start_is_422(client, agenda, starts_at, message):
    data = payload(agenda)
    data["starts_at"] = starts_at

    response = client.post("/appointments/", json=data, headers=agenda["headers"]["admin"])

    assert response.status_code == 422
    assert response.json()["errors"][0] == {"field": "starts_at", "message": message}


@pytest.mark.parametrize(("minutes", "message"), [(4, "Debe ser mayor o igual a 5."), (481, "Debe ser menor o igual a 480.")])
def test_duration_out_of_range_is_422(client, agenda, minutes, message):
    response = create(client, agenda, duration_minutes=minutes)

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == message


@pytest.mark.auth
def test_requires_session(client, agenda):
    assert client.post("/appointments/", json=payload(agenda)).status_code == 401
    assert client.get("/appointments/", params=day_range()).status_code == 401


# --- Cruces (ODON-136) ---------------------------------------------------------------

def test_doctor_overlap_is_409_with_the_conflicting_appointment(client, agenda):
    existing = created_id(client, agenda)

    response = create(client, agenda, patient_id=agenda["patients"][1], starts_at=NINE + timedelta(minutes=15))

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "Dr. Clinica Citas ya tiene una cita que se cruza con ese horario."
    conflict = body["conflict"]
    assert conflict["appointment_id"] == existing
    assert datetime.fromisoformat(conflict["starts_at"]) == NINE
    assert datetime.fromisoformat(conflict["ends_at"]) == NINE + timedelta(minutes=30)
    assert conflict["doctor_name"] == "Dr. Clinica Citas"
    assert conflict["patient_name"] == "Paciente0 Agenda"


def test_patient_overlap_with_other_doctor_is_409(client, agenda):
    existing = created_id(client, agenda)

    response = create(client, agenda, doctor_id=agenda["second"], starts_at=NINE + timedelta(minutes=10))

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "El paciente ya tiene una cita con Dr. Clinica Citas que se cruza con ese horario."
    assert body["conflict"]["appointment_id"] == existing
    assert body["conflict"]["doctor_id"] == agenda["doctor"]


def test_doctor_conflict_is_reported_before_patient_conflict(client, agenda):
    created_id(client, agenda, patient_id=agenda["patients"][1])
    created_id(client, agenda, doctor_id=agenda["second"], starts_at=NINE + timedelta(minutes=30))

    # Choca con el doctor (09:00) y con el propio paciente (09:30 con la segunda doctora).
    response = create(client, agenda, starts_at=NINE + timedelta(minutes=15), duration_minutes=30)

    assert response.json()["detail"].startswith("Dr. Clinica Citas ya tiene")


def test_back_to_back_is_allowed(client, agenda):
    created_id(client, agenda)

    assert create(client, agenda, patient_id=agenda["patients"][1], starts_at=NINE + timedelta(minutes=30)).status_code == 201
    assert create(client, agenda, patient_id=agenda["patients"][2], starts_at=NINE - timedelta(minutes=30)).status_code == 201


@pytest.mark.parametrize("status", ["cancelled", "no_show"])
def test_freed_slot_can_be_reused(client, agenda, db, status):
    set_status(db, created_id(client, agenda), status)

    assert create(client, agenda, patient_id=agenda["patients"][1]).status_code == 201


@pytest.mark.isolation
def test_other_clinic_does_not_block_the_slot(client, agenda):
    other = client.post(
        "/appointments/",
        json={"patient_id": agenda["foreign_patient"], "doctor_id": agenda["foreign_doctor"], "starts_at": iso(NINE)},
        headers=agenda["headers"]["other"],
    )
    assert other.status_code == 201

    assert create(client, agenda).status_code == 201


# --- Consulta ------------------------------------------------------------------------

def test_detail_and_404(client, agenda):
    appointment_id = created_id(client, agenda)

    assert client.get(f"/appointments/{appointment_id}", headers=agenda["headers"]["doctor"]).status_code == 200
    missing = client.get("/appointments/999999", headers=agenda["headers"]["doctor"])
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Cita no encontrada."


@pytest.mark.isolation
def test_detail_of_other_clinic_is_404(client, agenda):
    appointment_id = created_id(client, agenda)

    assert client.get(f"/appointments/{appointment_id}", headers=agenda["headers"]["other"]).status_code == 404


def test_list_by_range_includes_partial_overlaps_in_order(client, agenda):
    late = created_id(client, agenda, starts_at=NINE.replace(hour=16))
    early = created_id(client, agenda, patient_id=agenda["patients"][1], starts_at=NINE)
    # Empieza el día anterior a las 23:45 y termina a las 00:15: también aparece.
    crossing = created_id(client, agenda, patient_id=agenda["patients"][2], starts_at=NINE.replace(hour=0) - timedelta(minutes=15))
    created_id(client, agenda, patient_id=agenda["patients"][3], starts_at=NINE + timedelta(days=1))

    response = listing(client, agenda, **day_range())

    assert response.status_code == 200
    assert [a["id"] for a in response.json()] == [crossing, early, late]


def test_list_filters_by_doctor_patient_and_status(client, agenda, db):
    mine = created_id(client, agenda)
    other_doctor = created_id(client, agenda, patient_id=agenda["patients"][1], doctor_id=agenda["second"])
    cancelled = created_id(client, agenda, patient_id=agenda["patients"][2], starts_at=NINE + timedelta(hours=2))
    set_status(db, cancelled, "cancelled")

    ids = lambda **p: [a["id"] for a in listing(client, agenda, **day_range(), **p).json()]  # noqa: E731

    assert ids(doctor_id=agenda["doctor"]) == [mine, cancelled]
    assert ids(patient_id=agenda["patients"][1]) == [other_doctor]
    assert ids(status=["scheduled", "confirmed"]) == [mine, other_doctor]
    assert ids(status="cancelled") == [cancelled]


def test_list_by_patient_without_range(client, agenda):
    first = created_id(client, agenda)
    second = created_id(client, agenda, starts_at=NINE + timedelta(days=30))

    response = listing(client, agenda, patient_id=agenda["patient"])

    assert [a["id"] for a in response.json()] == [first, second]


@pytest.mark.isolation
def test_list_never_includes_other_clinic(client, agenda):
    created_id(client, agenda)

    assert listing(client, agenda, "other", **day_range()).json() == []
    assert listing(client, agenda, "other", patient_id=agenda["patient"]).json() == []


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({}, "Indica un rango de fechas o un paciente."),
        ({"start": iso(NINE)}, "Indica el inicio y el fin del rango."),
        ({"start": iso(NINE), "end": iso(NINE)}, "El fin del rango debe ser posterior al inicio."),
        ({"start": iso(NINE), "end": iso(NINE + timedelta(days=94))}, "El rango no puede superar 93 días."),
        ({"start": NINE.replace(tzinfo=None).isoformat(), "end": iso(NINE + timedelta(days=1))}, "El parámetro start debe incluir la zona horaria."),
    ],
)
def test_invalid_list_parameters(client, agenda, params, detail):
    response = listing(client, agenda, **params)

    assert response.status_code == 422
    assert response.json()["detail"] == detail


def test_unknown_status_filter_is_422(client, agenda):
    response = listing(client, agenda, **day_range(), status="pendiente")

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == "Valor no permitido."


# --- Reprogramación (ODON-135) -------------------------------------------------------

def patch(client, agenda, appointment_id, changes, role="receptionist"):
    return client.patch(f"/appointments/{appointment_id}", json=changes, headers=agenda["headers"][role])


@pytest.mark.rbac
@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_reschedule(client, agenda, role):
    appointment_id = created_id(client, agenda)

    response = patch(client, agenda, appointment_id, {"starts_at": iso(NINE + timedelta(hours=1)), "duration_minutes": 45, "doctor_id": agenda["second"], "reason": "Control"}, role)

    assert response.status_code == 200, response.text
    body = response.json()
    assert datetime.fromisoformat(body["starts_at"]) == NINE + timedelta(hours=1)
    assert body["duration_minutes"] == 45
    assert body["doctor_id"] == agenda["second"]
    assert body["reason"] == "Control"


def test_extending_over_own_slot_is_allowed(client, agenda):
    appointment_id = created_id(client, agenda)

    response = patch(client, agenda, appointment_id, {"starts_at": iso(NINE + timedelta(minutes=15)), "duration_minutes": 60})

    assert response.status_code == 200


def test_rescheduling_into_a_busy_slot_is_409(client, agenda):
    created_id(client, agenda)
    other = created_id(client, agenda, patient_id=agenda["patients"][1], starts_at=NINE + timedelta(hours=1))

    by_time = patch(client, agenda, other, {"starts_at": iso(NINE + timedelta(minutes=20))})
    by_duration = patch(client, agenda, other, {"starts_at": iso(NINE + timedelta(minutes=30)), "duration_minutes": 31})

    assert by_time.status_code == 409
    assert by_duration.status_code == 200  # 09:30-10:01 no choca con 09:00-09:30


def test_changing_to_a_busy_doctor_is_409(client, agenda):
    created_id(client, agenda, doctor_id=agenda["second"], patient_id=agenda["patients"][1])
    appointment_id = created_id(client, agenda)

    response = patch(client, agenda, appointment_id, {"doctor_id": agenda["second"]})

    assert response.status_code == 409
    assert response.json()["detail"] == "Dra. Segunda ya tiene una cita que se cruza con ese horario."


@pytest.mark.parametrize(
    ("changes", "status", "detail"),
    [
        ({"doctor_id": None}, 422, "Doctor, inicio y duración son obligatorios."),
        ({"doctor_id": "retired"}, 422, "El doctor seleccionado está inactivo."),
        ({"doctor_id": "foreign_doctor"}, 422, "El doctor seleccionado no pertenece a la clínica."),
        ({"starts_at": "past"}, 422, "La cita no puede empezar en el pasado."),
    ],
)
def test_invalid_reschedule(client, agenda, changes, status, detail):
    appointment_id = created_id(client, agenda)
    resolved = {}
    for key, value in changes.items():
        if value == "past":
            value = iso(datetime.now(GT).replace(second=0, microsecond=0) - timedelta(hours=1))
        elif isinstance(value, str):
            value = agenda[value]
        resolved[key] = value

    response = patch(client, agenda, appointment_id, resolved)

    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_patient_cannot_be_changed(client, agenda, db):
    appointment_id = created_id(client, agenda)

    patch(client, agenda, appointment_id, {"patient_id": agenda["patients"][1]})

    assert db.get(Appointment, appointment_id).patient_id == agenda["patient"]


@pytest.mark.parametrize("status", ["completed", "cancelled", "no_show"])
def test_only_pending_appointments_can_be_modified(client, agenda, db, status):
    appointment_id = created_id(client, agenda)
    set_status(db, appointment_id, status)

    response = patch(client, agenda, appointment_id, {"reason": "Otro"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Solo se pueden modificar citas programadas o confirmadas."


def test_reason_of_pending_appointment_can_change_without_revalidating(client, agenda, db):
    appointment_id = created_id(client, agenda)
    retired = db.get(Doctor, agenda["retired"])
    # Cita existente con un doctor que luego se desactivó: el motivo sigue editable.
    db.get(Appointment, appointment_id).doctor_id = retired.id
    db.commit()

    response = patch(client, agenda, appointment_id, {"reason": "Cambio de motivo"})

    assert response.status_code == 200


@pytest.mark.isolation
def test_cannot_reschedule_other_clinic_appointment(client, agenda):
    appointment_id = created_id(client, agenda)

    response = patch(client, agenda, appointment_id, {"reason": "x"}, "other")

    assert response.status_code == 404


def test_audit_logs_only_ids(client, agenda, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        appointment_id = created_id(client, agenda, reason="Dolor de muela")
        patch(client, agenda, appointment_id, {"reason": "Limpieza"})

    messages = [r.getMessage() for r in caplog.records if r.name == "odontonet.audit"]
    assert [m.split()[0] for m in messages] == ["appointment.created", "appointment.updated"]
    assert "fields=reason" in messages[1]
    assert not any(word in " ".join(messages) for word in ("Paciente0", "Dolor", "Limpieza", "5555"))


# --- Archivo de pacientes con citas (decisión del 2026-11-02) ------------------------

@pytest.mark.patients
def test_patient_with_upcoming_appointment_cannot_be_archived(client, agenda):
    created_id(client, agenda)

    response = client.post(f"/patients/{agenda['patient']}/archive", headers=agenda["headers"]["admin"])

    assert response.status_code == 409
    assert response.json()["detail"] == "El paciente tiene 1 cita próxima. Cancélala o reprográmala antes de archivarlo."


@pytest.mark.patients
def test_archive_message_counts_upcoming_appointments(client, agenda, db):
    created_id(client, agenda)
    confirmed = created_id(client, agenda, starts_at=NINE + timedelta(days=1))
    set_status(db, confirmed, "confirmed")

    response = client.post(f"/patients/{agenda['patient']}/archive", headers=agenda["headers"]["admin"])

    assert response.json()["detail"] == "El paciente tiene 2 citas próximas. Cancélalas o reprográmalas antes de archivarlo."


@pytest.mark.patients
@pytest.mark.parametrize("status", ["cancelled", "no_show", "completed"])
def test_closed_appointments_do_not_block_archiving(client, agenda, db, status):
    set_status(db, created_id(client, agenda), status)

    assert client.post(f"/patients/{agenda['patient']}/archive", headers=agenda["headers"]["admin"]).status_code == 200


@pytest.mark.patients
def test_past_pending_appointment_does_not_block_archiving(client, agenda, db):
    db.add(Appointment(
        clinic_id=agenda["clinic"], patient_id=agenda["patient"], doctor_id=agenda["doctor"],
        starts_at=datetime.now(GT) - timedelta(days=3), duration_minutes=30, created_by_user_id=agenda["doctor_user"],
    ))
    db.commit()

    assert client.post(f"/patients/{agenda['patient']}/archive", headers=agenda["headers"]["admin"]).status_code == 200


@pytest.mark.patients
def test_archived_patient_appointments_cannot_be_rescheduled(client, agenda, db):
    appointment_id = created_id(client, agenda)
    db.get(Patient, agenda["patient"]).archived_at = datetime.now(timezone.utc)
    db.commit()

    response = patch(client, agenda, appointment_id, {"starts_at": iso(NINE + timedelta(hours=3))})

    assert response.status_code == 409
    assert response.json()["detail"] == "El paciente está archivado. Reactívalo para agendarle citas."


# --- Concurrencia (ODON-137) ---------------------------------------------------------

def test_database_overlap_is_translated_when_validation_is_skipped(client, agenda, monkeypatch):
    """Simula la carrera: la validación previa no ve la otra cita; la base sí."""
    created_id(client, agenda)
    monkeypatch.setattr(appointment_routes, "ensure_no_overlap", lambda *args, **kwargs: None)

    by_doctor = create(client, agenda, patient_id=agenda["patients"][1])
    by_patient = create(client, agenda, doctor_id=agenda["second"])

    assert by_doctor.status_code == 409
    assert by_doctor.json()["detail"] == "El doctor ya tiene una cita que se cruza con ese horario."
    assert by_patient.status_code == 409
    assert by_patient.json()["detail"] == "El paciente ya tiene una cita que se cruza con ese horario."
    # Sin detalle de la otra cita: llegó en paralelo y no hay datos fiables.
    assert "conflict" not in by_doctor.json()


def test_simultaneous_requests_book_the_slot_only_once(agenda, db):
    patients = agenda["patients"][:5]
    barrier = threading.Barrier(len(patients))

    def book(patient_id):
        with TestClient(app) as own_client:
            barrier.wait()
            return own_client.post(
                "/appointments/",
                json=payload(agenda, patient_id=patient_id),
                headers=agenda["headers"]["receptionist"],
            ).status_code

    with ThreadPoolExecutor(max_workers=len(patients)) as pool:
        codes = sorted(pool.map(book, patients))

    assert codes == [201, 409, 409, 409, 409]
    assert db.query(Appointment).count() == 1
