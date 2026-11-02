"""Estados, transiciones e historial de citas (ODON-146 / ODON-147 y ODON-149)."""
import logging
from datetime import datetime, timedelta

import pytest

from app.models import Appointment, AppointmentStatusChange, Patient
from tests.appointment_fixtures import (  # noqa: F401  (agenda es un fixture)
    GT,
    NINE,
    ROLES,
    agenda,
    create,
    created_id,
    iso,
    listing,
)

pytestmark = [pytest.mark.appointments]


def change(client, agenda, appointment_id, status, note=None, role="receptionist"):
    body = {"status": status}
    if note is not None:
        body["note"] = note
    return client.post(f"/appointments/{appointment_id}/status", json=body, headers=agenda["headers"][role])


def history(client, agenda, appointment_id, role="receptionist"):
    response = client.get(f"/appointments/{appointment_id}/history", headers=agenda["headers"][role])
    assert response.status_code == 200, response.text
    return response.json()


def past_appointment(db, agenda, status="scheduled", hours_ago=3, patient_index=0):
    """Cita que ya empezó (o terminó): se inserta directo porque la API no
    permite agendar en el pasado."""
    appointment = Appointment(
        clinic_id=agenda["clinic"], patient_id=agenda["patients"][patient_index], doctor_id=agenda["doctor"],
        starts_at=datetime.now(GT).replace(second=0, microsecond=0) - timedelta(hours=hours_ago),
        duration_minutes=30, status=status, created_by_user_id=agenda["doctor_user"],
    )
    db.add(appointment)
    db.commit()
    return appointment.id


# --- Confirmar y cancelar (lo que hace recepción al llamar) --------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ROLES)
def test_every_role_can_confirm(client, agenda, role):
    appointment_id = created_id(client, agenda)

    response = change(client, agenda, appointment_id, "confirmed", "Confirmó por teléfono", role)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "confirmed"


def test_confirmation_can_be_undone(client, agenda):
    appointment_id = created_id(client, agenda)
    change(client, agenda, appointment_id, "confirmed")

    assert change(client, agenda, appointment_id, "scheduled").json()["status"] == "scheduled"


@pytest.mark.parametrize("start", ["scheduled", "confirmed"])
def test_pending_appointments_can_be_cancelled_and_free_the_slot(client, agenda, start):
    appointment_id = created_id(client, agenda)
    if start == "confirmed":
        change(client, agenda, appointment_id, "confirmed")

    response = change(client, agenda, appointment_id, "cancelled", "Paciente de viaje")

    assert response.json()["status"] == "cancelled"
    assert create(client, agenda, patient_id=agenda["patients"][1]).status_code == 201


def test_repeating_the_current_status_changes_nothing(client, agenda):
    appointment_id = created_id(client, agenda)
    change(client, agenda, appointment_id, "confirmed")

    again = change(client, agenda, appointment_id, "confirmed")

    assert again.status_code == 200
    assert [h["to_status"] for h in history(client, agenda, appointment_id)] == ["scheduled", "confirmed"]


def test_listing_scheduled_finds_appointments_to_confirm(client, agenda):
    to_call = created_id(client, agenda)
    confirmed = created_id(client, agenda, patient_id=agenda["patients"][1], starts_at=NINE + timedelta(hours=1))
    change(client, agenda, confirmed, "confirmed")

    start = datetime.now(GT)
    response = listing(client, agenda, start=iso(start), end=iso(start + timedelta(days=7)), status="scheduled")

    assert [a["id"] for a in response.json()] == [to_call]
    assert response.json()[0]["patient"]["phone"] == "5555-0000"


# --- Atendida y No asistió -----------------------------------------------------------

@pytest.mark.parametrize("status", ["completed", "no_show"])
def test_started_appointment_can_be_closed(client, agenda, db, status):
    appointment_id = past_appointment(db, agenda, hours_ago=1)

    assert change(client, agenda, appointment_id, status, role="doctor").json()["status"] == status


@pytest.mark.parametrize("status", ["completed", "no_show"])
def test_future_appointment_cannot_be_closed(client, agenda, status):
    appointment_id = created_id(client, agenda)

    response = change(client, agenda, appointment_id, status)

    assert response.status_code == 409
    assert response.json()["detail"] == "La cita todavía no empieza: no se puede marcar como atendida o no asistió."


@pytest.mark.parametrize("status", ["confirmed", "cancelled", "scheduled"])
def test_finished_appointment_can_only_be_closed(client, agenda, db, status):
    appointment_id = past_appointment(db, agenda, status="confirmed" if status == "scheduled" else "scheduled")

    response = change(client, agenda, appointment_id, status)

    assert response.status_code == 409
    assert response.json()["detail"] == "La cita ya terminó: márcala como atendida o como no asistió."


def test_in_progress_appointment_can_still_be_confirmed_or_closed(client, agenda, db):
    # Empezó hace 10 minutos y dura 30: aún no termina.
    appointment_id = past_appointment(db, agenda, hours_ago=1 / 6)

    assert change(client, agenda, appointment_id, "confirmed").status_code == 200
    assert change(client, agenda, appointment_id, "completed").status_code == 200


def test_completed_and_no_show_can_be_corrected_between_them(client, agenda, db):
    appointment_id = past_appointment(db, agenda, status="completed")

    assert change(client, agenda, appointment_id, "no_show").json()["status"] == "no_show"
    assert change(client, agenda, appointment_id, "completed").json()["status"] == "completed"


@pytest.mark.parametrize(
    ("current", "target", "detail"),
    [
        ("completed", "scheduled", "Una cita atendida no puede pasar a programada."),
        ("completed", "cancelled", "Una cita atendida no puede pasar a cancelada."),
        ("no_show", "confirmed", "Una cita no asistió no puede pasar a confirmada."),
        ("cancelled", "confirmed", "Una cita cancelada no puede pasar a confirmada."),
        ("cancelled", "completed", "Una cita cancelada no puede pasar a atendida."),
    ],
)
def test_forbidden_transitions(client, agenda, db, current, target, detail):
    appointment_id = past_appointment(db, agenda, status=current)

    response = change(client, agenda, appointment_id, target)

    assert response.status_code == 409
    assert response.json()["detail"] == detail


# --- Reactivar una cancelada ---------------------------------------------------------

def test_cancelled_future_appointment_can_be_reactivated(client, agenda):
    appointment_id = created_id(client, agenda)
    change(client, agenda, appointment_id, "cancelled")

    response = change(client, agenda, appointment_id, "scheduled", "Volvió a llamar")

    assert response.json()["status"] == "scheduled"


def test_reactivation_fails_if_the_slot_was_taken(client, agenda):
    appointment_id = created_id(client, agenda)
    change(client, agenda, appointment_id, "cancelled")
    created_id(client, agenda, patient_id=agenda["patients"][1])

    response = change(client, agenda, appointment_id, "scheduled")

    assert response.status_code == 409
    assert response.json()["detail"] == "Dr. Clinica Citas ya tiene una cita que se cruza con ese horario."
    assert "conflict" in response.json()


def test_past_cancelled_appointment_cannot_be_reactivated(client, agenda, db):
    appointment_id = past_appointment(db, agenda, status="cancelled")

    response = change(client, agenda, appointment_id, "scheduled")

    assert response.status_code == 422
    assert response.json()["detail"] == "La cita no puede empezar en el pasado."


def test_reactivation_requires_active_doctor_and_patient(client, agenda, db):
    appointment_id = created_id(client, agenda)
    change(client, agenda, appointment_id, "cancelled")
    db.get(Appointment, appointment_id).doctor_id = agenda["retired"]
    db.commit()

    assert change(client, agenda, appointment_id, "scheduled").json()["detail"] == "El doctor seleccionado está inactivo."

    db.get(Appointment, appointment_id).doctor_id = agenda["doctor"]
    db.get(Patient, agenda["patient"]).archived_at = datetime.now(GT)
    db.commit()

    response = change(client, agenda, appointment_id, "scheduled")
    assert response.status_code == 409
    assert response.json()["detail"] == "El paciente está archivado. Reactívalo para agendarle citas."


# --- Validación, aislamiento e historial (ODON-149) -----------------------------------

def test_unknown_status_and_long_note_are_422(client, agenda):
    appointment_id = created_id(client, agenda)

    assert change(client, agenda, appointment_id, "pendiente").status_code == 422
    assert change(client, agenda, appointment_id, "confirmed", "x" * 256).status_code == 422


@pytest.mark.isolation
def test_other_clinic_cannot_change_or_read_history(client, agenda):
    appointment_id = created_id(client, agenda)

    assert change(client, agenda, appointment_id, "cancelled", role="other").status_code == 404
    assert client.get(f"/appointments/{appointment_id}/history", headers=agenda["headers"]["other"]).status_code == 404
    assert client.get("/appointments/999999/history", headers=agenda["headers"]["admin"]).status_code == 404


@pytest.mark.auth
def test_status_requires_session(client, agenda):
    appointment_id = created_id(client, agenda)

    assert client.post(f"/appointments/{appointment_id}/status", json={"status": "confirmed"}).status_code == 401


def test_history_records_every_change_with_author_and_note(client, agenda):
    appointment_id = created_id(client, agenda, role="receptionist")
    change(client, agenda, appointment_id, "confirmed", "  Confirmó por teléfono  ", "receptionist")
    change(client, agenda, appointment_id, "cancelled", "", "admin")

    entries = history(client, agenda, appointment_id, "doctor")

    assert [(e["from_status"], e["to_status"]) for e in entries] == [
        (None, "scheduled"), ("scheduled", "confirmed"), ("confirmed", "cancelled"),
    ]
    assert [e["note"] for e in entries] == [None, "Confirmó por teléfono", None]
    assert [e["changed_by"]["name"] for e in entries] == ["receptionist", "receptionist", "admin"]
    assert all(e["changed_at"] for e in entries)
    assert set(entries[0]["changed_by"]) == {"id", "name"}


def test_rescheduling_does_not_add_status_history(client, agenda):
    appointment_id = created_id(client, agenda)

    client.patch(f"/appointments/{appointment_id}", json={"reason": "Otro"}, headers=agenda["headers"]["admin"])

    assert len(history(client, agenda, appointment_id)) == 1


def test_failed_change_leaves_no_history(client, agenda, db):
    appointment_id = created_id(client, agenda)

    change(client, agenda, appointment_id, "completed")

    assert db.query(AppointmentStatusChange).filter_by(appointment_id=appointment_id).count() == 1


def test_status_change_is_audited_without_personal_data(client, agenda, caplog):
    appointment_id = created_id(client, agenda)
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        change(client, agenda, appointment_id, "confirmed", "Confirmó Paciente0 al 5555-0000")

    messages = [
        r.getMessage() for r in caplog.records
        if r.name == "odontonet.audit" and "status_changed" in r.getMessage()
    ]
    assert len(messages) == 1
    assert messages[0].startswith(f"appointment.status_changed appointment_id={appointment_id} user_id=")
    assert messages[0].endswith(f"clinic_id={agenda['clinic']} from=scheduled to=confirmed")
    assert "5555" not in messages[0] and "Paciente0" not in messages[0]


@pytest.mark.patients
def test_cancelling_upcoming_appointments_allows_archiving(client, agenda):
    appointment_id = created_id(client, agenda)
    assert client.post(f"/patients/{agenda['patient']}/archive", headers=agenda["headers"]["admin"]).status_code == 409

    change(client, agenda, appointment_id, "cancelled")

    assert client.post(f"/patients/{agenda['patient']}/archive", headers=agenda["headers"]["admin"]).status_code == 200
