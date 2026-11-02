"""Pruebas cruzadas entre dos clínicas (ODON-62 / ODON-65)."""
import pytest

from app.auth.security import hash_password
from app.models import User
from tests.conftest import PASSWORD, create_clinic_with_doctor

pytestmark = [pytest.mark.isolation]


def new_patient(**overrides):
    data = {"first_name": "Ana", "last_name": "Pérez", "email": "ana@test.com"}
    data.update(overrides)
    return data


# --- Autenticación obligatoria ----------------------------------------------

@pytest.mark.auth
@pytest.mark.patients
@pytest.mark.parametrize(
    "method,path",
    [("get", "/patients/"), ("post", "/patients/"), ("get", "/patients/1"),
     ("get", "/doctors/"), ("post", "/doctors/"), ("get", "/doctors/1")],
)
def test_endpoints_require_authentication(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code in (401, 403)


@pytest.mark.auth
def test_invalid_token_is_rejected(client):
    response = client.get("/patients/", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


@pytest.mark.auth
def test_token_of_deactivated_user_is_rejected(client, db):
    _, user, _ = create_clinic_with_doctor(db, "Clinica C", "inactive@test.com")
    token = client.post("/auth/login", json={"email": "inactive@test.com", "password": PASSWORD}).json()["access_token"]
    user.is_active = False
    db.commit()
    response = client.get("/patients/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# --- Pacientes ----------------------------------------------------------------

@pytest.mark.patients
def test_create_patient_takes_clinic_from_token(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    payload = new_patient(doctor_id=a["doctor"], clinic_id=b["clinic"])  # clinic_id ajeno se ignora

    response = client.post("/patients/", json=payload, headers=a["headers"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["clinic_id"] == a["clinic"]
    assert body["doctor"]["id"] == a["doctor"]


@pytest.mark.patients
def test_list_patients_only_returns_own_clinic(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    client.post("/patients/", json=new_patient(first_name="De A", email="a1@test.com"), headers=a["headers"])
    client.post("/patients/", json=new_patient(first_name="De B", email="b1@test.com"), headers=b["headers"])

    names_a = [p["first_name"] for p in client.get("/patients/", headers=a["headers"]).json()["items"]]
    names_b = [p["first_name"] for p in client.get("/patients/", headers=b["headers"]).json()["items"]]

    assert names_a == ["De A"]
    assert names_b == ["De B"]


@pytest.mark.patients
def test_patient_of_other_clinic_is_not_found(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    patient_id = client.post("/patients/", json=new_patient(), headers=b["headers"]).json()["id"]

    assert client.get(f"/patients/{patient_id}", headers=b["headers"]).status_code == 200
    response = client.get(f"/patients/{patient_id}", headers=a["headers"])
    assert response.status_code == 404
    assert "Ana" not in response.text


@pytest.mark.patients
def test_cannot_assign_doctor_of_other_clinic(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]

    response = client.post("/patients/", json=new_patient(doctor_id=b["doctor"]), headers=a["headers"])

    assert response.status_code == 422
    assert client.get("/patients/", headers=a["headers"]).json()["items"] == []


@pytest.mark.patients
def test_unknown_doctor_gets_same_error_as_foreign_doctor(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    foreign = client.post("/patients/", json=new_patient(doctor_id=b["doctor"]), headers=a["headers"])
    unknown = client.post("/patients/", json=new_patient(doctor_id=9999), headers=a["headers"])
    assert foreign.status_code == unknown.status_code == 422
    assert foreign.json() == unknown.json()


@pytest.mark.patients
def test_same_email_allowed_in_different_clinics(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    assert client.post("/patients/", json=new_patient(), headers=a["headers"]).status_code == 201
    assert client.post("/patients/", json=new_patient(), headers=b["headers"]).status_code == 201


@pytest.mark.patients
def test_duplicate_email_in_same_clinic_returns_conflict(client, two_clinics):
    a = two_clinics["a"]
    assert client.post("/patients/", json=new_patient(), headers=a["headers"]).status_code == 201
    response = client.post("/patients/", json=new_patient(), headers=a["headers"])
    assert response.status_code == 409


@pytest.mark.patients
def test_empty_optional_fields_are_stored_as_null(client, two_clinics):
    a = two_clinics["a"]
    payload = {"first_name": "Luis", "last_name": "Gómez", "email": "", "phone": "", "address": "", "birth_date": ""}

    first = client.post("/patients/", json=payload, headers=a["headers"])
    second = client.post("/patients/", json=payload, headers=a["headers"])

    assert first.status_code == second.status_code == 201, first.text
    assert first.json()["email"] is None
    assert first.json()["birth_date"] is None


@pytest.mark.parametrize(
    "payload",
    [{"first_name": "  ", "last_name": "X"}, {"first_name": "X", "last_name": "Y", "email": "no-es-correo"},
     {"first_name": "X", "last_name": "Y", "birth_date": "2999-01-01"}],
)
def test_invalid_patient_data_is_rejected(client, two_clinics, payload):
    response = client.post("/patients/", json=payload, headers=two_clinics["a"]["headers"])
    assert response.status_code == 422


# --- Doctores -----------------------------------------------------------------

@pytest.mark.doctors
def test_list_doctors_only_returns_own_clinic(client, two_clinics):
    a = two_clinics["a"]
    doctors = client.get("/doctors/", headers=a["headers"]).json()
    assert [d["id"] for d in doctors] == [a["doctor"]]
    assert all(d["clinic_id"] == a["clinic"] for d in doctors)


@pytest.mark.doctors
def test_doctor_of_other_clinic_is_not_found(client, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    assert client.get(f"/doctors/{b['doctor']}", headers=a["headers"]).status_code == 404


def promote_to_admin(db, user_id):
    db.query(User).filter(User.id == user_id).update({"role": "admin"})
    db.commit()


@pytest.mark.doctors
def test_create_doctor_profile_for_own_clinic_user(client, db, two_clinics):
    a = two_clinics["a"]
    promote_to_admin(db, a["user"])
    user = User(name="Nuevo", email="nuevo@test.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=a["clinic"])
    db.add(user)
    db.commit()

    response = client.post("/doctors/", json={"user_id": user.id}, headers=a["headers"])

    assert response.status_code == 201, response.text
    assert response.json()["clinic_id"] == a["clinic"]
    duplicate = client.post("/doctors/", json={"user_id": user.id}, headers=a["headers"])
    assert duplicate.status_code == 409


@pytest.mark.doctors
def test_cannot_create_doctor_profile_for_user_of_other_clinic(client, db, two_clinics):
    a, b = two_clinics["a"], two_clinics["b"]
    promote_to_admin(db, a["user"])
    user = User(name="Ajeno", email="ajeno@test.com", hashed_password=hash_password(PASSWORD), role="doctor", clinic_id=b["clinic"])
    db.add(user)
    db.commit()

    response = client.post("/doctors/", json={"user_id": user.id}, headers=a["headers"])

    assert response.status_code == 422
