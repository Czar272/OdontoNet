"""Listado de doctores con datos de usuario y filtro de activos (ODON-82 / ODON-85)."""
import pytest

from app.auth.security import hash_password
from app.models import Clinic, Doctor, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.doctors]


@pytest.fixture
def clinic(db, client):
    """Clínica con tres doctores (uno inactivo) y una recepcionista; otra
    clínica con su propio doctor."""
    main = Clinic(name="Clinica Listado")
    other = Clinic(name="Clinica Vecina")
    db.add_all([main, other])
    db.flush()

    def add_doctor(clinic_id, name, email, specialization, active=True):
        user = User(
            name=name,
            email=email,
            hashed_password=hash_password(PASSWORD),
            role="doctor",
            is_active=active,
            clinic_id=clinic_id,
        )
        db.add(user)
        db.flush()
        doctor = Doctor(user_id=user.id, clinic_id=clinic_id, specialization=specialization, license_number=f"COL-{user.id}")
        db.add(doctor)
        db.flush()
        return doctor

    zoila = add_doctor(main.id, "Dra. Zoila Ruiz", "zoila@listado-clinica.com", "Periodoncia")
    bruno = add_doctor(main.id, "Dr. Bruno Alvarado", "bruno@listado-clinica.com", "Ortodoncia")
    retired = add_doctor(main.id, "Dr. Carlos Inactivo", "carlos@listado-clinica.com", "Endodoncia", active=False)
    foreign = add_doctor(other.id, "Dra. Vecina", "vecina@vecina-clinica.com", "General")
    db.add(User(
        name="Recepción",
        email="recepcion@listado-clinica.com",
        hashed_password=hash_password(PASSWORD),
        role="receptionist",
        clinic_id=main.id,
    ))
    db.commit()

    return {
        "ids": {"zoila": zoila.id, "bruno": bruno.id, "retired": retired.id, "foreign": foreign.id},
        "headers": auth_headers(client, "recepcion@listado-clinica.com"),
    }


def names(response):
    return [doctor["user"]["name"] for doctor in response.json()]


def test_list_includes_name_and_specialization_sorted_by_name(client, clinic):
    response = client.get("/doctors/", headers=clinic["headers"])

    assert response.status_code == 200
    assert names(response) == ["Dr. Bruno Alvarado", "Dr. Carlos Inactivo", "Dra. Zoila Ruiz"]
    zoila = next(d for d in response.json() if d["id"] == clinic["ids"]["zoila"])
    assert zoila["specialization"] == "Periodoncia"
    assert zoila["user"]["is_active"] is True


def test_list_never_exposes_password(client, clinic):
    for doctor in client.get("/doctors/", headers=clinic["headers"]).json():
        assert "password" not in doctor["user"] and "hashed_password" not in doctor["user"]


def test_active_filter(client, clinic):
    active = client.get("/doctors/", params={"active": "true"}, headers=clinic["headers"])
    inactive = client.get("/doctors/", params={"active": "false"}, headers=clinic["headers"])

    assert names(active) == ["Dr. Bruno Alvarado", "Dra. Zoila Ruiz"]
    assert names(inactive) == ["Dr. Carlos Inactivo"]


def test_active_filter_rejects_invalid_value(client, clinic):
    assert client.get("/doctors/", params={"active": "quizas"}, headers=clinic["headers"]).status_code == 422


@pytest.mark.isolation
@pytest.mark.parametrize("active", [None, "true", "false"])
def test_every_filter_stays_in_own_clinic(client, clinic, active):
    params = {"active": active} if active else {}

    response = client.get("/doctors/", params=params, headers=clinic["headers"])

    assert "Dra. Vecina" not in names(response)
    assert clinic["ids"]["foreign"] not in {doctor["id"] for doctor in response.json()}


@pytest.mark.isolation
def test_foreign_doctor_detail_is_not_found(client, clinic):
    assert client.get(f"/doctors/{clinic['ids']['foreign']}", headers=clinic["headers"]).status_code == 404


def test_inactive_doctor_detail_is_still_available(client, clinic):
    response = client.get(f"/doctors/{clinic['ids']['retired']}", headers=clinic["headers"])

    assert response.status_code == 200
    assert response.json()["user"]["is_active"] is False


@pytest.mark.patients
def test_cannot_assign_new_patient_to_inactive_doctor(client, clinic):
    payload = {"first_name": "Nora", "last_name": "Soto", "doctor_id": clinic["ids"]["retired"]}

    response = client.post("/patients/", json=payload, headers=clinic["headers"])

    assert response.status_code == 422
    assert response.json()["detail"] == "El doctor seleccionado está inactivo."


@pytest.mark.patients
def test_can_assign_new_patient_to_active_doctor(client, clinic):
    payload = {"first_name": "Nora", "last_name": "Soto", "doctor_id": clinic["ids"]["zoila"]}

    response = client.post("/patients/", json=payload, headers=clinic["headers"])

    assert response.status_code == 201
    assert response.json()["doctor"]["user"]["name"] == "Dra. Zoila Ruiz"
