"""Modelo Appointment, integridad en la base y schemas (ODON-130 / ODON-133)."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Appointment, Doctor, Patient, User
from app.schemas.appointment_schema import AppointmentCreate, AppointmentResponse, AppointmentUpdate
from tests.conftest import create_clinic_with_doctor

pytestmark = [pytest.mark.appointments]

GT = timezone(timedelta(hours=-6))  # America/Guatemala (sin horario de verano)
NINE = datetime(2026, 11, 3, 9, 0, tzinfo=GT)


@pytest.fixture
def agenda(db):
    clinic, user, doctor = create_clinic_with_doctor(db, "Clinica Agenda", "doc@agenda-clinica.com")
    _, other_user, other_doctor = create_clinic_with_doctor(db, "Clinica Otra Agenda", "doc@otra-agenda.com")
    second_user = User(name="Dra. Dos", email="dos@agenda-clinica.com", hashed_password="x", role="doctor", clinic_id=clinic.id)
    db.add(second_user)
    db.flush()
    second = Doctor(user_id=second_user.id, clinic_id=clinic.id)
    patient = Patient(first_name="Ana", last_name="Cita", clinic_id=clinic.id)
    other_patient = Patient(first_name="Otro", last_name="Paciente", clinic_id=clinic.id)
    foreign_patient = Patient(first_name="Ajeno", last_name="X", clinic_id=other_doctor.clinic_id)
    db.add_all([second, patient, other_patient, foreign_patient])
    db.commit()
    return {
        "clinic": clinic.id, "user": user.id, "doctor": doctor.id, "second": second.id,
        "patient": patient.id, "other_patient": other_patient.id,
        "foreign_doctor": other_doctor.id, "foreign_patient": foreign_patient.id,
    }


def make(agenda, starts_at=NINE, minutes=30, **overrides):
    data = {
        "clinic_id": agenda["clinic"], "patient_id": agenda["patient"], "doctor_id": agenda["doctor"],
        "starts_at": starts_at, "duration_minutes": minutes, "created_by_user_id": agenda["user"],
    }
    data.update(overrides)
    return Appointment(**data)


def save(db, *appointments):
    db.add_all(appointments)
    db.commit()


def assert_rejected(db, appointment, constraint):
    db.add(appointment)
    with pytest.raises(IntegrityError) as error:
        db.commit()
    db.rollback()
    assert constraint in str(error.value.orig)


# --- Modelo y valores por defecto (ODON-131) -----------------------------------------

def test_defaults_and_computed_end(db, agenda):
    appointment = make(agenda, minutes=45, reason="Limpieza")
    save(db, appointment)
    db.refresh(appointment)

    assert appointment.status == "scheduled"
    assert appointment.created_at is not None
    assert appointment.updated_at is not None
    assert appointment.ends_at == NINE + timedelta(minutes=45)
    assert appointment.patient.first_name == "Ana"
    assert appointment.doctor.id == agenda["doctor"]


def test_starts_at_keeps_the_instant_across_time_zones(db, agenda):
    save(db, make(agenda))

    stored = db.query(Appointment).one()

    assert stored.starts_at == datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)


def test_sql_end_function_matches_model(db, agenda):
    appointment = make(agenda, minutes=50)
    save(db, appointment)

    end = db.execute(select(func.appointment_end(Appointment.starts_at, Appointment.duration_minutes))).scalar_one()
    assert end == appointment.ends_at


# --- Cruces de horario (ex_appointments_doctor_overlap) ------------------------------

@pytest.mark.parametrize(
    ("start_offset", "minutes"),
    [(0, 30), (15, 30), (-15, 30), (5, 10), (-60, 120)],
)
def test_overlapping_appointments_of_same_doctor_are_rejected(db, agenda, start_offset, minutes):
    save(db, make(agenda))

    overlapping = make(agenda, starts_at=NINE + timedelta(minutes=start_offset), minutes=minutes, patient_id=agenda["other_patient"])

    assert_rejected(db, overlapping, "ex_appointments_doctor_overlap")


def test_overlap_is_detected_across_time_zones(db, agenda):
    save(db, make(agenda))

    same_instant_utc = make(agenda, starts_at=datetime(2026, 11, 3, 15, 10, tzinfo=timezone.utc), patient_id=agenda["other_patient"])

    assert_rejected(db, same_instant_utc, "ex_appointments_doctor_overlap")


def test_back_to_back_appointments_are_allowed(db, agenda):
    save(db, make(agenda), make(agenda, starts_at=NINE + timedelta(minutes=30), patient_id=agenda["other_patient"]))

    assert db.query(Appointment).count() == 2


def test_other_doctor_can_have_the_same_slot(db, agenda):
    save(db, make(agenda), make(agenda, doctor_id=agenda["second"], patient_id=agenda["other_patient"]))

    assert db.query(Appointment).count() == 2


@pytest.mark.parametrize("status", ["cancelled", "no_show"])
def test_cancelled_and_no_show_free_the_slot(db, agenda, status):
    save(db, make(agenda, status=status), make(agenda, patient_id=agenda["other_patient"]))

    assert db.query(Appointment).count() == 2


@pytest.mark.parametrize("status", ["confirmed", "completed"])
def test_confirmed_and_completed_keep_the_slot(db, agenda, status):
    save(db, make(agenda, status=status))

    assert_rejected(db, make(agenda, patient_id=agenda["other_patient"]), "ex_appointments_doctor_overlap")


def test_reactivating_a_freed_slot_is_rejected_if_taken(db, agenda):
    cancelled = make(agenda, status="cancelled")
    save(db, cancelled, make(agenda, patient_id=agenda["other_patient"]))

    cancelled.status = "scheduled"
    with pytest.raises(IntegrityError) as error:
        db.commit()
    db.rollback()

    assert "ex_appointments_doctor_overlap" in str(error.value.orig)


# --- Otras restricciones de la base --------------------------------------------------

@pytest.mark.isolation
def test_patient_must_be_from_the_same_clinic(db, agenda):
    assert_rejected(db, make(agenda, patient_id=agenda["foreign_patient"]), "fk_appointments_patient_clinic")


@pytest.mark.isolation
def test_doctor_must_be_from_the_same_clinic(db, agenda):
    assert_rejected(db, make(agenda, doctor_id=agenda["foreign_doctor"]), "fk_appointments_doctor_clinic")


@pytest.mark.parametrize("minutes", [0, 4, 481])
def test_duration_out_of_range_is_rejected(db, agenda, minutes):
    assert_rejected(db, make(agenda, minutes=minutes), "ck_appointments_duration")


def test_unknown_status_is_rejected(db, agenda):
    assert_rejected(db, make(agenda, status="pendiente"), "ck_appointments_status")


@pytest.mark.patients
def test_patient_with_appointments_cannot_be_deleted(db, agenda):
    save(db, make(agenda))

    db.delete(db.get(Patient, agenda["patient"]))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    assert db.get(Patient, agenda["patient"]) is not None


# --- Schemas (ODON-133) --------------------------------------------------------------

def test_create_schema_defaults():
    data = AppointmentCreate(patient_id=1, doctor_id=2, starts_at="2026-11-03T09:30:00-06:00", reason="   ")

    assert data.duration_minutes == 30
    assert data.reason is None
    assert data.starts_at.utcoffset() == timedelta(hours=-6)
    assert "status" not in data.model_dump()
    assert "clinic_id" not in data.model_dump()


@pytest.mark.parametrize(
    ("starts_at", "message"),
    [
        ("2026-11-03T09:30:00", "La fecha y hora deben incluir la zona horaria."),
        ("2026-11-03T09:30:15-06:00", "La hora debe ser exacta al minuto."),
    ],
)
def test_create_schema_rejects_ambiguous_times(starts_at, message):
    with pytest.raises(ValidationError) as error:
        AppointmentCreate(patient_id=1, doctor_id=2, starts_at=starts_at)

    assert str(error.value.errors()[0]["ctx"]["error"]) == message


@pytest.mark.parametrize("minutes", [4, 481])
def test_create_schema_rejects_duration_out_of_range(minutes):
    with pytest.raises(ValidationError):
        AppointmentCreate(patient_id=1, doctor_id=2, starts_at=NINE, duration_minutes=minutes)


def test_create_schema_rejects_long_reason():
    with pytest.raises(ValidationError):
        AppointmentCreate(patient_id=1, doctor_id=2, starts_at=NINE, reason="x" * 256)


def test_update_schema_is_partial_and_has_no_patient_or_status():
    changes = AppointmentUpdate(duration_minutes=60)

    assert changes.model_dump(exclude_unset=True) == {"duration_minutes": 60}
    assert "patient_id" not in AppointmentUpdate.model_fields
    assert "status" not in AppointmentUpdate.model_fields


def test_update_schema_validates_starts_at():
    with pytest.raises(ValidationError):
        AppointmentUpdate(starts_at="2026-11-03T09:30:00")


def test_response_schema_exposes_end_and_minimal_patient(db, agenda):
    appointment = make(agenda, minutes=45, reason="Control")
    save(db, appointment)
    db.refresh(appointment)

    body = AppointmentResponse.model_validate(appointment).model_dump()

    assert body["ends_at"] == NINE + timedelta(minutes=45)
    assert body["status"] == "scheduled"
    assert set(body["patient"]) == {"id", "first_name", "last_name", "phone", "archived_at"}
    assert "hashed_password" not in body["doctor"]["user"]
