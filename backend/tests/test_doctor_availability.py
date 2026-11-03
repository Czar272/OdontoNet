"""Horario semanal de doctores y aviso de citas fuera de horario (ODON-142 / ODON-143 y 144)."""
import logging
from datetime import datetime, timedelta

import pytest

from app.models import Clinic
from app.models.availability import WEEKDAY_LABELS
from tests.appointment_fixtures import (  # noqa: F401  (agenda es un fixture)
    NINE,
    agenda,
    create,
    created_id,
    iso,
)

pytestmark = [pytest.mark.doctors]

SPLIT_DAY = [("08:00", "12:00"), ("14:00", "18:00")]


def week(ranges=SPLIT_DAY, days=range(7)):
    return [{"weekday": d, "start_time": s, "end_time": e} for d in days for s, e in ranges]


def put(client, agenda, doctor_key, blocks, role="admin"):
    return client.put(
        f"/doctors/{agenda[doctor_key]}/availability", json={"blocks": blocks}, headers=agenda["headers"][role]
    )


# --- Consultar y editar (ODON-143) ---------------------------------------------------

def test_clinic_availability_starts_empty_with_clinic_timezone(client, agenda):
    response = client.get("/doctors/availability", headers=agenda["headers"]["receptionist"])

    assert response.status_code == 200
    body = {d["doctor_id"]: d for d in response.json()}
    assert set(body) == {agenda["doctor"], agenda["second"], agenda["retired"]}
    assert all(d["blocks"] == [] and d["timezone"] == "America/Guatemala" for d in body.values())


@pytest.mark.rbac
@pytest.mark.parametrize("role", ["admin", "receptionist"])
def test_admin_and_reception_edit_any_schedule(client, agenda, role):
    response = put(client, agenda, "second", week(days=[2, 0]), role)

    assert response.status_code == 200, response.text
    blocks = response.json()["blocks"]
    # Ordenados por día y hora, aunque se envíen desordenados.
    assert [(b["weekday"], b["start_time"]) for b in blocks] == [
        (0, "08:00:00"), (0, "14:00:00"), (2, "08:00:00"), (2, "14:00:00"),
    ]


@pytest.mark.rbac
def test_doctor_edits_only_own_schedule(client, agenda):
    own = put(client, agenda, "doctor", week(days=[0]), "doctor")
    other = put(client, agenda, "second", week(days=[0]), "doctor")

    assert own.status_code == 200
    assert other.status_code == 403
    assert other.json()["detail"] == "Solo puedes editar tu propio horario."


def test_put_replaces_and_empty_list_clears(client, agenda):
    put(client, agenda, "doctor", week())
    put(client, agenda, "doctor", week(ranges=[("09:00", "10:00")], days=[4]))

    assert len(client.get(f"/doctors/{agenda['doctor']}/availability", headers=agenda["headers"]["doctor"]).json()["blocks"]) == 1
    assert put(client, agenda, "doctor", []).json()["blocks"] == []


@pytest.mark.parametrize(
    ("blocks", "message"),
    [
        ([{"weekday": 0, "start_time": "12:00", "end_time": "08:00"}], "La hora de fin debe ser posterior a la de inicio."),
        ([{"weekday": 0, "start_time": "08:00", "end_time": "08:00"}], "La hora de fin debe ser posterior a la de inicio."),
        ([{"weekday": 7, "start_time": "08:00", "end_time": "09:00"}], "Debe ser menor o igual a 6."),
        ([{"weekday": 0, "start_time": "08:00:30", "end_time": "09:00"}], "La hora debe ser exacta al minuto."),
        (week(ranges=[("08:00", "12:00"), ("11:00", "13:00")], days=[0]), "Los bloques del lunes se cruzan."),
    ],
)
def test_invalid_schedule_is_422(client, agenda, blocks, message):
    response = put(client, agenda, "doctor", blocks)

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == message


def test_back_to_back_blocks_are_valid(client, agenda):
    assert put(client, agenda, "doctor", week(ranges=[("08:00", "12:00"), ("12:00", "13:00")], days=[0])).status_code == 200


@pytest.mark.isolation
def test_other_clinic_doctor_is_404(client, agenda):
    assert client.get(f"/doctors/{agenda['foreign_doctor']}/availability", headers=agenda["headers"]["admin"]).status_code == 404
    assert put(client, agenda, "foreign_doctor", week()).status_code == 404
    assert agenda["foreign_doctor"] not in {d["doctor_id"] for d in client.get("/doctors/availability", headers=agenda["headers"]["admin"]).json()}


def test_schedule_change_is_audited(client, agenda, caplog):
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        put(client, agenda, "doctor", week())

    assert any(f"doctor.availability_updated doctor_id={agenda['doctor']}" in r.getMessage() and "blocks=14" in r.getMessage() for r in caplog.records)


# --- Citas fuera de horario: avisar y permitir (ODON-144) ----------------------------

def day_name(when: datetime) -> str:
    return WEEKDAY_LABELS[when.weekday()]


@pytest.mark.appointments
def test_doctor_without_schedule_is_free(client, agenda):
    assert create(client, agenda, starts_at=NINE.replace(hour=22)).status_code == 201


@pytest.mark.appointments
def test_inside_schedule_is_accepted(client, agenda):
    put(client, agenda, "doctor", week())

    assert create(client, agenda, starts_at=NINE).status_code == 201
    assert create(client, agenda, starts_at=NINE.replace(hour=17, minute=30), patient_id=agenda["patients"][1]).status_code == 201


@pytest.mark.appointments
@pytest.mark.parametrize(("hour", "minute"), [(12, 30), (7, 30), (11, 45), (17, 45)])
def test_outside_or_crossing_the_schedule_warns(client, agenda, hour, minute):
    put(client, agenda, "doctor", week())
    when = NINE.replace(hour=hour, minute=minute)

    response = create(client, agenda, starts_at=when)

    assert response.status_code == 409
    body = response.json()
    assert body["outside_schedule"] is True
    assert body["detail"] == (
        f"Dr. Clinica Citas no atiende en ese horario. Su horario del {day_name(when)} es 08:00–12:00 y 14:00–18:00."
    )


@pytest.mark.appointments
def test_day_without_blocks_says_so(client, agenda):
    other_days = [d for d in range(7) if d != NINE.weekday()]
    put(client, agenda, "doctor", week(days=other_days))

    detail = create(client, agenda).json()["detail"]

    day = day_name(NINE)
    plural = day + "s" if day in ("sábado", "domingo") else day
    assert detail == f"Dr. Clinica Citas no atiende en ese horario. No atiende los {plural}."


@pytest.mark.appointments
def test_confirmed_outside_schedule_is_saved(client, agenda):
    put(client, agenda, "doctor", week())

    response = create(client, agenda, starts_at=NINE.replace(hour=13), allow_outside_schedule=True)

    assert response.status_code == 201
    assert "allow_outside_schedule" not in response.json()


@pytest.mark.appointments
def test_hard_errors_come_before_the_schedule_warning(client, agenda):
    put(client, agenda, "doctor", week())
    created_id(client, agenda, starts_at=NINE.replace(hour=13), allow_outside_schedule=True)

    response = create(client, agenda, starts_at=NINE.replace(hour=13), patient_id=agenda["patients"][1])

    assert response.status_code == 409
    assert "outside_schedule" not in response.json()
    assert response.json()["detail"].startswith("Dr. Clinica Citas ya tiene una cita")


@pytest.mark.appointments
def test_rescheduling_checks_the_schedule(client, agenda):
    put(client, agenda, "doctor", week())
    appointment_id = created_id(client, agenda)
    url = f"/appointments/{appointment_id}"
    headers = agenda["headers"]["receptionist"]

    warned = client.patch(url, json={"starts_at": iso(NINE.replace(hour=13))}, headers=headers)
    forced = client.patch(url, json={"starts_at": iso(NINE.replace(hour=13)), "allow_outside_schedule": True}, headers=headers)
    reason_only = client.patch(url, json={"reason": "Control"}, headers=headers)

    assert warned.status_code == 409 and warned.json()["outside_schedule"] is True
    assert forced.status_code == 200
    # Solo cambia el motivo: no se vuelve a revisar el horario.
    assert reason_only.status_code == 200


@pytest.mark.appointments
def test_changing_to_a_doctor_with_other_schedule_warns(client, agenda):
    put(client, agenda, "second", week(ranges=[("14:00", "18:00")]))
    appointment_id = created_id(client, agenda)

    response = client.patch(f"/appointments/{appointment_id}", json={"doctor_id": agenda["second"]}, headers=agenda["headers"]["admin"])

    assert response.status_code == 409
    assert response.json()["detail"].startswith("Dra. Segunda no atiende en ese horario.")


@pytest.mark.appointments
def test_schedule_uses_the_clinic_timezone(client, agenda, db):
    clinic = db.get(Clinic, agenda["clinic"])
    clinic.timezone = "America/New_York"  # UTC-5 en noviembre; Guatemala es UTC-6
    db.commit()
    put(client, agenda, "doctor", week(ranges=[("10:00", "11:00")]))

    # 09:00 en Guatemala son las 10:00 en Nueva York: dentro del bloque.
    assert create(client, agenda, starts_at=NINE).status_code == 201
    # 10:30 en Guatemala son las 11:30 en Nueva York: fuera.
    assert create(client, agenda, starts_at=NINE + timedelta(minutes=90), patient_id=agenda["patients"][1]).status_code == 409


@pytest.mark.appointments
def test_inactive_doctor_schedule_can_still_be_read(client, agenda):
    response = client.get(f"/doctors/{agenda['retired']}/availability", headers=agenda["headers"]["receptionist"])

    assert response.status_code == 200
    assert response.json()["blocks"] == []
