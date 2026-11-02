"""Seed sintético de desarrollo (ODON-34 / ODON-35 / ODON-36)."""
import pytest

from app.models import Appointment, AppointmentStatusChange, Clinic, Doctor, Patient, User
from scripts.seed_dev import (
    CLINICS,
    PATIENTS_PER_CLINIC,
    STAFF,
    SeedError,
    ensure_development,
    read_password,
    seed,
    staff_email,
    validate_relations,
)
from tests.conftest import create_clinic_with_doctor

pytestmark = [pytest.mark.seed]


PASSWORD = "Demo-Password-123"


def counts(db):
    return {
        "clinics": db.query(Clinic).count(),
        "users": db.query(User).count(),
        "doctors": db.query(Doctor).count(),
        "patients": db.query(Patient).count(),
        "appointments": db.query(Appointment).count(),
    }


def test_seed_creates_related_data(db):
    created = seed(db, PASSWORD)

    appointments = created.pop("appointments")
    assert created == {
        "clinics": len(CLINICS),
        "users": len(CLINICS) * len(STAFF),
        "doctors": len(CLINICS) * 2,
        "patients": len(CLINICS) * PATIENTS_PER_CLINIC,
    }
    # 14 días alrededor de hoy: entre 9 y 10 hábiles, 6 citas por día y clínica.
    assert len(CLINICS) * 6 * 9 <= appointments <= len(CLINICS) * 6 * 10
    validate_relations(db)


def test_seed_is_idempotent(db):
    seed(db, PASSWORD)
    before = counts(db)

    second = seed(db, PASSWORD)

    assert second == {"clinics": 0, "users": 0, "doctors": 0, "patients": 0, "appointments": 0}
    assert counts(db) == before


def test_seed_does_not_touch_existing_data(db):
    clinic, user, _ = create_clinic_with_doctor(db, "Clinica Existente", "existente@clinica.com")

    seed(db, PASSWORD)

    assert db.query(Clinic).filter(Clinic.id == clinic.id).one().name == "Clinica Existente"
    assert db.query(User).filter(User.id == user.id).one().email == "existente@clinica.com"


@pytest.mark.isolation
def test_seeded_users_log_in_and_see_only_their_clinic(client, db):
    seed(db, PASSWORD)

    for spec in CLINICS:
        login = client.post("/auth/login", json={"email": staff_email("recepcion", spec["slug"]), "password": PASSWORD})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        patients = client.get("/patients/", headers=headers).json()["items"]
        assert len(patients) == PATIENTS_PER_CLINIC
        assert all(spec["slug"] in p["email"] for p in patients)


@pytest.mark.rbac
def test_seeded_roles_match_permissions(client, db):
    seed(db, PASSWORD)
    slug = CLINICS[0]["slug"]

    def headers(prefix):
        token = client.post("/auth/login", json={"email": staff_email(prefix, slug), "password": PASSWORD}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    payload = {"name": "Nuevo", "email": "nuevo.demo@odontonet-demo.com", "password": "Segura-123"}
    assert client.post("/auth/register", json=payload, headers=headers("recepcion")).status_code == 403
    assert client.post("/auth/register", json=payload, headers=headers("admin")).status_code == 201


@pytest.mark.parametrize(
    "url,environment",
    [
        ("postgresql://u:p@db.example.com:5432/odontonet", "development"),
        ("postgresql://u:p@10.0.0.5:5432/odontonet", "development"),
        ("postgresql://u:p@localhost:5432/odontonet", "production"),
    ],
)
def test_refuses_outside_development(url, environment):
    with pytest.raises(SeedError):
        ensure_development(url, environment)


def test_accepts_local_development_database():
    ensure_development("postgresql://u:p@localhost:5432/odontonet", "development")
    ensure_development("postgresql+psycopg2://u:p@127.0.0.1:5432/odontonet", "development")


@pytest.mark.parametrize("value", [None, "", "corta"])
def test_requires_strong_enough_password(value):
    with pytest.raises(SeedError):
        read_password(value)


@pytest.mark.appointments
def test_seeded_agenda_is_coherent(db):
    seed(db, PASSWORD)

    for clinic in db.query(Clinic).all():
        appointments = db.query(Appointment).filter(Appointment.clinic_id == clinic.id).all()
        assert appointments
        assert all(a.patient.clinic_id == clinic.id and a.doctor.clinic_id == clinic.id for a in appointments)
        statuses = {a.status for a in appointments}
        assert {"completed", "scheduled"} <= statuses
        assert all([c.to_status for c in a.status_changes] == [a.status] for a in appointments)


@pytest.mark.appointments
def test_seed_does_not_add_appointments_to_an_existing_agenda(db):
    # Simula una clínica con una sola cita propia (no del seed).
    seed(db, PASSWORD)
    keep = db.query(Appointment.id).order_by(Appointment.id).first().id
    db.query(AppointmentStatusChange).delete()
    db.query(Appointment).filter(Appointment.id != keep).delete()
    db.commit()
    before = db.query(Appointment).count()

    created = seed(db, PASSWORD)["appointments"]

    # La clínica con su cita no recibe la agenda demo; la otra, sin citas, sí.
    assert db.query(Appointment).count() == before + created
    assert created == 60
