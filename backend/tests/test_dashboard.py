"""Panel de inicio: indicadores, periodo, filtro por doctor, aislamiento y roles (ODON-202)."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.auth.security import hash_password
from app.models.appointment import Appointment
from app.models.availability import DoctorAvailabilityBlock
from app.models.clinical_visit import ClinicalVisit
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.periodontal import PeriodontalExam
from app.models.treatment import Treatment, TreatmentStatusChange
from app.models.user import User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.dashboard]

GT = ZoneInfo("America/Guatemala")  # UTC−6, sin horario de verano
MARCH = {"from": "2026-03-01", "to": "2026-03-31"}


def local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), GT)


@pytest.fixture
def setup(db, client):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Panel", "doc@panel-clinica.com")
    other_clinic, _, other_doctor = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-panel.com")
    colleague_user = User(name="Dra. Colega", email="colega@panel-clinica.com", hashed_password=hash_password(PASSWORD),
                          role="doctor", clinic_id=clinic.id)
    db.add_all([
        colleague_user,
        User(name="Admin Panel", email="admin@panel-clinica.com", hashed_password=hash_password(PASSWORD),
             role="admin", clinic_id=clinic.id),
        User(name="Recepción", email="recepcion@panel-clinica.com", hashed_password=hash_password(PASSWORD),
             role="receptionist", clinic_id=clinic.id),
    ])
    db.flush()
    colleague = Doctor(user_id=colleague_user.id, clinic_id=clinic.id)
    db.add(colleague)
    db.flush()
    patient = Patient(first_name="Ana", last_name="Ríos", clinic_id=clinic.id, doctor_id=doctor.id)
    second_patient = Patient(first_name="Beto", last_name="Luna", clinic_id=clinic.id)
    other_patient = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([patient, second_patient, other_patient])
    db.commit()
    headers = {
        "doctor": auth_headers(client, "doc@panel-clinica.com"),
        "admin": auth_headers(client, "admin@panel-clinica.com"),
        "receptionist": auth_headers(client, "recepcion@panel-clinica.com"),
        "other": auth_headers(client, "doc@ajena-panel.com"),
    }
    return {
        "db": db, "clinic": clinic, "other_clinic": other_clinic, "doctor": doctor, "doctor_user": doctor_user,
        "colleague": colleague, "other_doctor": other_doctor, "patient": patient, "second_patient": second_patient, "other_patient": other_patient,
        "headers": headers,
    }


def add_appointment(s, starts_at, status="scheduled", duration=30, doctor=None, patient=None, clinic=None):
    doctor = doctor or s["doctor"]
    appointment = Appointment(
        clinic_id=(clinic or s["clinic"]).id, patient_id=(patient or s["patient"]).id, doctor_id=doctor.id,
        starts_at=starts_at, duration_minutes=duration, status=status, created_by_user_id=s["doctor_user"].id,
    )
    s["db"].add(appointment)
    s["db"].commit()
    return appointment


def get(client, s, role="doctor", **params):
    return client.get("/dashboard", params=params, headers=s["headers"][role])


# --- Acceso -------------------------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ["doctor", "admin", "receptionist"])
def test_all_roles_see_dashboard(client, setup, role):
    response = get(client, setup, role, **MARCH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"date_from", "date_to", "timezone", "doctor_id", "indicators", "agenda_today"}


@pytest.mark.rbac
def test_requires_authentication(client, setup):
    assert client.get("/dashboard").status_code == 401


@pytest.mark.isolation
def test_other_clinic_data_is_not_counted(client, setup):
    add_appointment(setup, local(date(2026, 3, 10), 9), "completed",
                    doctor=setup["other_doctor"], patient=setup["other_patient"], clinic=setup["other_clinic"])
    body = get(client, setup, "admin", **MARCH).json()
    assert body["indicators"]["appointments_period"] == 0
    assert body["indicators"]["patients_active"] == 2
    other = get(client, setup, "other", **MARCH).json()
    assert other["indicators"]["appointments_period"] == 1
    assert other["indicators"]["patients_active"] == 1


@pytest.mark.isolation
def test_doctor_from_other_clinic_is_404(client, setup):
    response = get(client, setup, "admin", doctor_id=setup["other_doctor"].id, **MARCH)
    assert response.status_code == 404
    assert response.json()["detail"] == "Doctor no encontrado."


# --- Periodo ------------------------------------------------------------------

def test_default_period_is_current_month_in_clinic_timezone(client, setup):
    body = get(client, setup).json()
    today = datetime.now(timezone.utc).astimezone(GT).date()
    assert body["date_from"] == today.replace(day=1).isoformat()
    end = date.fromisoformat(body["date_to"])
    assert end.month == today.month and (end + timedelta(days=1)).day == 1
    assert body["timezone"] == "America/Guatemala"


def test_only_from_extends_to_end_of_that_month(client, setup):
    body = get(client, setup, **{"from": "2026-02-10"}).json()
    assert body["date_to"] == "2026-02-28"


@pytest.mark.parametrize("params", [
    {"from": "2026-03-10", "to": "2026-03-01"},
    {"from": "2025-01-01", "to": "2026-03-01"},
])
def test_invalid_period_is_422(client, setup, params):
    assert get(client, setup, **params).status_code == 422


def test_period_uses_clinic_local_days(client, setup):
    # 31-mar 21:00 en Guatemala = 1-abr 03:00 UTC: cuenta en marzo, no en abril.
    add_appointment(setup, local(date(2026, 3, 31), 21), "completed")
    assert get(client, setup, **MARCH).json()["indicators"]["appointments_period"] == 1
    april = get(client, setup, **{"from": "2026-04-01", "to": "2026-04-30"}).json()
    assert april["indicators"]["appointments_period"] == 0


# --- Indicadores --------------------------------------------------------------

def test_appointment_rates(client, setup):
    day = date(2026, 3, 10)
    for hour, status in ((8, "completed"), (9, "completed"), (10, "completed"), (11, "no_show"),
                         (12, "cancelled"), (13, "scheduled")):
        add_appointment(setup, local(day, hour), status)
    indicators = get(client, setup, **MARCH).json()["indicators"]
    assert indicators["appointments_period"] == 6
    assert indicators["attendance_rate"] == 75.0
    assert indicators["no_show_rate"] == 25.0
    assert indicators["cancellation_rate"] == 16.7


def test_rates_are_null_without_data(client, setup):
    indicators = get(client, setup, **MARCH).json()["indicators"]
    assert indicators["attendance_rate"] is None
    assert indicators["no_show_rate"] is None
    assert indicators["cancellation_rate"] is None
    assert indicators["occupancy_rate"] is None


def test_doctor_filter(client, setup):
    day = date(2026, 3, 10)
    add_appointment(setup, local(day, 8), "completed")
    add_appointment(setup, local(day, 8), "no_show", doctor=setup["colleague"])
    all_doctors = get(client, setup, "admin", **MARCH).json()
    assert all_doctors["doctor_id"] is None
    assert all_doctors["indicators"]["appointments_period"] == 2
    mine = get(client, setup, "admin", doctor_id=setup["doctor"].id, **MARCH).json()
    assert mine["doctor_id"] == setup["doctor"].id
    assert mine["indicators"]["appointments_period"] == 1
    assert mine["indicators"]["attendance_rate"] == 100.0
    # Pacientes a cargo del doctor: el colega no tiene ninguno.
    colleague = get(client, setup, "admin", doctor_id=setup["colleague"].id, **MARCH).json()
    assert colleague["indicators"]["patients_active"] == 0


def test_new_patients_need_registration_date(client, setup):
    db = setup["db"]
    # Paciente anterior a la fecha de alta: no cuenta como nuevo en ningún periodo.
    db.query(Patient).filter(Patient.id == setup["patient"].id).update({"created_at": None})
    db.add_all([
        Patient(first_name="Nuevo", last_name="Marzo", clinic_id=setup["clinic"].id,
                created_at=local(date(2026, 3, 15), 10)),
        Patient(first_name="Nuevo", last_name="Febrero", clinic_id=setup["clinic"].id,
                created_at=local(date(2026, 2, 15), 10)),
        Patient(first_name="Archivado", last_name="Marzo", clinic_id=setup["clinic"].id,
                created_at=local(date(2026, 3, 16), 10), archived_at=datetime.now(timezone.utc)),
    ])
    db.commit()
    indicators = get(client, setup, **MARCH).json()["indicators"]
    assert indicators["patients_new"] == 2
    assert indicators["patients_active"] == 4


def test_new_patient_gets_registration_date(client, setup):
    response = client.post("/patients", json={"first_name": "Alta", "last_name": "Hoy"},
                           headers=setup["headers"]["admin"])
    assert response.status_code == 201, response.text
    created = setup["db"].get(Patient, response.json()["id"])
    assert created.created_at is not None
    # Los dos de la fixture también se crearon hoy.
    assert get(client, setup).json()["indicators"]["patients_new"] == 3


def test_occupancy(client, setup):
    # Lunes 08:00–12:00: marzo de 2026 tiene 5 lunes → 1200 minutos.
    setup["db"].add(DoctorAvailabilityBlock(clinic_id=setup["clinic"].id, doctor_id=setup["doctor"].id,
                                            weekday=0, start_time=time(8), end_time=time(12)))
    setup["db"].commit()
    monday = date(2026, 3, 2)
    add_appointment(setup, local(monday, 8), "completed", duration=60)
    add_appointment(setup, local(monday, 9), "scheduled", duration=60)
    add_appointment(setup, local(monday, 10), "cancelled", duration=60)
    add_appointment(setup, local(monday, 11), "no_show", duration=60)
    indicators = get(client, setup, **MARCH).json()["indicators"]
    assert indicators["occupancy_rate"] == 10.0
    # El colega no tiene horario: su ocupación no se puede calcular.
    colleague = get(client, setup, doctor_id=setup["colleague"].id, **MARCH).json()
    assert colleague["indicators"]["occupancy_rate"] is None
    # Sus citas tampoco inflan la ocupación de la clínica.
    add_appointment(setup, local(monday, 8), "completed", duration=240, doctor=setup["colleague"],
                    patient=setup["second_patient"])
    assert get(client, setup, **MARCH).json()["indicators"]["occupancy_rate"] == 10.0


def test_occupancy_ignores_deactivated_doctors(client, setup):
    db = setup["db"]
    db.add(DoctorAvailabilityBlock(clinic_id=setup["clinic"].id, doctor_id=setup["doctor"].id,
                                   weekday=0, start_time=time(8), end_time=time(12)))
    db.add(DoctorAvailabilityBlock(clinic_id=setup["clinic"].id, doctor_id=setup["colleague"].id,
                                   weekday=0, start_time=time(8), end_time=time(12)))
    db.commit()
    add_appointment(setup, local(date(2026, 3, 2), 8), "completed", duration=120)
    add_appointment(setup, local(date(2026, 3, 2), 8), "completed", duration=240, doctor=setup["colleague"],
                    patient=setup["second_patient"])
    assert get(client, setup, **MARCH).json()["indicators"]["occupancy_rate"] == 15.0
    db.query(User).filter(User.id == setup["colleague"].user_id).update({"is_active": False})
    db.commit()
    assert get(client, setup, **MARCH).json()["indicators"]["occupancy_rate"] == 10.0


def test_day_boundaries_follow_daylight_saving(db):
    from app.services.dashboard_service import Period, local_midnight
    zone = ZoneInfo("America/New_York")
    # 8-mar-2026: cambio a horario de verano; ese día local dura 23 horas.
    day = date(2026, 3, 8)
    assert local_midnight(day + timedelta(days=1), zone) - local_midnight(day, zone) == timedelta(hours=23)
    period = Period(day, day, zone)
    assert period.end - period.start == timedelta(hours=23)


def test_clinical_activity_counts(client, setup):
    db = setup["db"]
    s = setup
    visit_at = local(date(2026, 3, 5), 10)
    visit = ClinicalVisit(clinic_id=s["clinic"].id, patient_id=s["patient"].id, visit_at=visit_at,
                          doctor_id=s["doctor"].id, reason="Control", created_by_user_id=s["doctor_user"].id)
    voided = ClinicalVisit(clinic_id=s["clinic"].id, patient_id=s["patient"].id, visit_at=visit_at,
                           doctor_id=s["doctor"].id, reason="Error", created_by_user_id=s["doctor_user"].id,
                           voided_at=visit_at, voided_by_user_id=s["doctor_user"].id, void_reason="Duplicada")
    db.add_all([visit, voided])
    db.flush()
    treatment = Treatment(clinic_id=s["clinic"].id, patient_id=s["patient"].id, procedure="Profilaxis",
                          status="completed", completed_visit_id=visit.id,
                          created_by_user_id=s["doctor_user"].id, updated_by_user_id=s["doctor_user"].id)
    db.add(treatment)
    db.flush()
    db.add(TreatmentStatusChange(clinic_id=s["clinic"].id, treatment_id=treatment.id, from_status="in_progress",
                                 to_status="completed", changed_by_user_id=s["doctor_user"].id,
                                 changed_at=visit_at))
    db.add(PeriodontalExam(clinic_id=s["clinic"].id, patient_id=s["patient"].id, exam_date=date(2026, 3, 5),
                           status="final", created_by_user_id=s["doctor_user"].id,
                           finalized_at=visit_at, finalized_by_user_id=s["doctor_user"].id))
    db.add(PeriodontalExam(clinic_id=s["clinic"].id, patient_id=s["patient"].id, exam_date=date(2026, 3, 6),
                           status="draft", created_by_user_id=s["doctor_user"].id))
    db.commit()

    indicators = get(client, s, **MARCH).json()["indicators"]
    assert indicators["visits_registered"] == 1
    assert indicators["treatments_completed"] == 1
    assert indicators["periodontal_finalized"] == 1
    assert indicators["images_uploaded"] == 0

    colleague = get(client, s, doctor_id=s["colleague"].id, **MARCH).json()["indicators"]
    assert colleague["visits_registered"] == 0
    assert colleague["treatments_completed"] == 0
    assert colleague["periodontal_finalized"] == 0


# --- Agenda de hoy ------------------------------------------------------------

def test_agenda_today(client, setup):
    today = datetime.now(timezone.utc).astimezone(GT).date()
    first = add_appointment(setup, local(today, 9), "confirmed")
    add_appointment(setup, local(today, 10), "cancelled")
    add_appointment(setup, local(today, 8), "scheduled", doctor=setup["colleague"])
    add_appointment(setup, local(today, 9), "scheduled", doctor=setup["other_doctor"],
                    patient=setup["other_patient"], clinic=setup["other_clinic"])
    add_appointment(setup, local(today - timedelta(days=1), 9), "completed")

    body = get(client, setup, "receptionist").json()
    agenda = body["agenda_today"]
    assert [item["doctor"]["id"] for item in agenda] == [setup["colleague"].id, setup["doctor"].id]
    assert agenda[1]["id"] == first.id
    assert agenda[1]["patient"] == {"id": setup["patient"].id, "name": "Ana Ríos"}
    assert agenda[1]["doctor"]["name"] == "Dr. Clinica Panel"
    assert body["indicators"]["appointments_today"] == 2

    mine = get(client, setup, doctor_id=setup["doctor"].id).json()
    assert [item["id"] for item in mine["agenda_today"]] == [first.id]
    assert mine["indicators"]["appointments_today"] == 1
