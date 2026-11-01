"""Modelo Clinic y relaciones de datos (ODON-58 / ODON-59 a ODON-61)."""
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.database.connection import engine
from app.models import Clinic, Doctor, Patient, User
from scripts.seed_dev import CLINICS, seed, validate_relations
from tests.conftest import create_clinic_with_doctor

pytestmark = [pytest.mark.isolation]

CLINIC_SCOPED_TABLES = ("users", "doctors", "patients")


# --- Esquema (ODON-59) -----------------------------------------------------------

@pytest.mark.parametrize("table", CLINIC_SCOPED_TABLES)
def test_table_has_required_clinic_fk(table):
    inspector = inspect(engine)

    column = next(c for c in inspector.get_columns(table) if c["name"] == "clinic_id")
    fks = [fk for fk in inspector.get_foreign_keys(table) if fk["constrained_columns"] == ["clinic_id"]]

    assert column["nullable"] is False
    assert len(fks) == 1 and fks[0]["referred_table"] == "clinics" and fks[0]["referred_columns"] == ["id"]


def test_expected_constraints_exist():
    inspector = inspect(engine)
    uniques = {
        table: {u["name"] for u in inspector.get_unique_constraints(table)}
        for table in ("users", "doctors", "patients")
    }
    fks = {fk["name"] for fk in inspector.get_foreign_keys("doctors")}

    assert {"uq_users_id_clinic"} <= uniques["users"]
    assert {"uq_doctors_user_id"} <= uniques["doctors"]
    assert {"uq_patients_clinic_email"} <= uniques["patients"]
    assert "fk_doctors_user_clinic" in fks


@pytest.mark.parametrize("table", ("doctors", "patients"))
def test_clinic_id_is_indexed(table):
    indexed = {tuple(index["column_names"]) for index in inspect(engine).get_indexes(table)}

    assert ("clinic_id",) in indexed


# --- Relaciones ORM (ODON-60) --------------------------------------------------------

def test_clinic_relationships_return_own_records(db):
    clinic_a, user_a, doctor_a = create_clinic_with_doctor(db, "Clinica Uno", "uno@modelo-clinica.com")
    clinic_b, _, _ = create_clinic_with_doctor(db, "Clinica Dos", "dos@modelo-clinica.com")
    db.add(Patient(first_name="Ana", last_name="Paz", clinic_id=clinic_a.id, doctor_id=doctor_a.id))
    db.commit()

    db.refresh(clinic_a)
    db.refresh(clinic_b)

    assert [u.id for u in clinic_a.users] == [user_a.id]
    assert [d.id for d in clinic_a.doctors] == [doctor_a.id]
    assert [p.first_name for p in clinic_a.patients] == ["Ana"]
    assert clinic_b.patients == []
    assert clinic_a.patients[0].doctor.user.clinic is clinic_a


@pytest.mark.parametrize("model", [User, Doctor, Patient])
def test_records_require_existing_clinic(db, model):
    fields = {
        User: {"name": "X", "email": "x@modelo-clinica.com", "hashed_password": "x", "role": "doctor"},
        Doctor: {"user_id": 1},
        Patient: {"first_name": "X", "last_name": "Y"},
    }[model]
    db.add(model(clinic_id=999_999, **fields))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_clinic_with_data_cannot_be_deleted(db):
    clinic, _, _ = create_clinic_with_doctor(db, "Clinica Con Datos", "datos@modelo-clinica.com")

    db.delete(db.get(Clinic, clinic.id))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.get(Clinic, clinic.id) is not None


# --- Seed coherente (ODON-61) ----------------------------------------------------------

@pytest.mark.seed
def test_seed_is_coherent_per_clinic(db):
    seed(db, "Demo-Password-123")
    validate_relations(db)

    clinics = db.query(Clinic).all()
    assert len(clinics) == len(CLINICS)
    for clinic in clinics:
        roles = {u.role for u in clinic.users}
        assert {"admin", "doctor", "receptionist"} <= roles
        assert all(d.user.clinic_id == clinic.id for d in clinic.doctors)
        assert all(p.doctor is None or p.doctor.clinic_id == clinic.id for p in clinic.patients)
