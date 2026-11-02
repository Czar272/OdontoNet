"""Modelo Patient, relación doctor–clínica y listado eficiente (ODON-98 / ODON-102)."""
import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError

from app.database.connection import engine
from app.models import Doctor, Patient
from tests.conftest import auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.patients]


@pytest.fixture
def clinics(db, client):
    clinic_a, user_a, doctor_a = create_clinic_with_doctor(db, "Clinica Pacientes A", "a@pacientes-clinica.com")
    clinic_b, _, doctor_b = create_clinic_with_doctor(db, "Clinica Pacientes B", "b@pacientes-clinica.com")
    return {
        "a": clinic_a.id,
        "b": clinic_b.id,
        "doctor_a": doctor_a.id,
        "doctor_b": doctor_b.id,
        "headers": auth_headers(client, "a@pacientes-clinica.com"),
    }


# --- Esquema y FKs (ODON-99 / ODON-101) -----------------------------------------

def test_patient_foreign_keys():
    fks = {fk["name"]: fk for fk in inspect(engine).get_foreign_keys("patients")}
    composite = fks["fk_patients_doctor_clinic"]

    assert composite["constrained_columns"] == ["doctor_id", "clinic_id"]
    assert composite["referred_table"] == "doctors"
    assert composite["referred_columns"] == ["id", "clinic_id"]
    assert {"uq_doctors_id_clinic"} <= {u["name"] for u in inspect(engine).get_unique_constraints("doctors")}


def test_doctor_is_optional(db, clinics):
    column = next(c for c in inspect(engine).get_columns("patients") if c["name"] == "doctor_id")
    db.add(Patient(first_name="Sin", last_name="Doctor", clinic_id=clinics["a"]))
    db.commit()

    assert column["nullable"] is True


# --- Consistencia doctor–clínica (ODON-100) ---------------------------------------

@pytest.mark.isolation
def test_database_rejects_doctor_from_other_clinic(db, clinics):
    db.add(Patient(first_name="Cruzado", last_name="X", clinic_id=clinics["a"], doctor_id=clinics["doctor_b"]))

    with pytest.raises(IntegrityError, match="fk_patients_doctor_clinic"):
        db.commit()
    db.rollback()


def test_database_accepts_doctor_from_same_clinic(db, clinics):
    db.add(Patient(first_name="Bien", last_name="Asignado", clinic_id=clinics["a"], doctor_id=clinics["doctor_a"]))
    db.commit()


@pytest.mark.isolation
def test_api_rejects_doctor_from_other_clinic(client, clinics):
    payload = {"first_name": "Ana", "last_name": "Paz", "doctor_id": clinics["doctor_b"]}

    response = client.post("/patients/", json=payload, headers=clinics["headers"])

    assert response.status_code == 422
    assert response.json()["detail"] == "El doctor seleccionado no pertenece a la clínica."


def test_duplicate_email_still_conflicts(client, clinics):
    payload = {"first_name": "Ana", "last_name": "Paz", "email": "ana@paz.com"}
    client.post("/patients/", json=payload, headers=clinics["headers"])

    assert client.post("/patients/", json=payload, headers=clinics["headers"]).status_code == 409


# --- Listado (ODON-102) ---------------------------------------------------------------

def test_list_shows_name_contact_and_doctor(client, clinics, db):
    db.add(Patient(first_name="Lía", last_name="Rey", phone="5555-1111", email="lia@rey.com", clinic_id=clinics["a"], doctor_id=clinics["doctor_a"]))
    db.add(Patient(first_name="Otro", last_name="Ajeno", clinic_id=clinics["b"], doctor_id=clinics["doctor_b"]))
    db.commit()

    body = client.get("/patients/", headers=clinics["headers"]).json()["items"]

    assert len(body) == 1
    patient = body[0]
    assert (patient["first_name"], patient["last_name"], patient["phone"], patient["email"]) == ("Lía", "Rey", "5555-1111", "lia@rey.com")
    assert patient["doctor"]["user"]["name"] == "Dr. Clinica Pacientes A"
    assert "hashed_password" not in patient["doctor"]["user"]


def _count_queries(client, headers) -> int:
    statements = []

    def before_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_execute)
    try:
        assert client.get("/patients/", headers=headers).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", before_execute)
    return len(statements)


def test_list_query_count_does_not_grow_with_patients(client, clinics, db):
    db.add(Patient(first_name="Uno", last_name="Solo", clinic_id=clinics["a"], doctor_id=clinics["doctor_a"]))
    db.commit()
    with_one = _count_queries(client, clinics["headers"])

    db.add_all([
        Patient(first_name=f"P{i}", last_name="Lote", clinic_id=clinics["a"], doctor_id=clinics["doctor_a"])
        for i in range(25)
    ])
    db.commit()
    with_many = _count_queries(client, clinics["headers"])

    # Doctor y usuario se cargan con joins: sin consultas N+1.
    assert with_many == with_one
