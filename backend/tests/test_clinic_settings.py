"""Administración básica de la clínica (ODON-74 / ODON-77)."""
import pytest

from app.auth.security import hash_password
from app.models import Clinic, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.isolation]

ROLES = ("admin", "doctor", "receptionist")


@pytest.fixture
def clinics(db, client):
    norte = Clinic(name="Clínica Norte", address="Zona 1", phone="2222-0000", email="norte@clinica.com")
    sur = Clinic(name="Clínica Sur", address="Zona 9")
    db.add_all([norte, sur])
    db.flush()
    for role in ROLES:
        db.add(User(name=role, email=f"{role}@norte-ajustes.com", hashed_password=hash_password(PASSWORD), role=role, clinic_id=norte.id))
    db.add(User(name="admin sur", email="admin@sur-ajustes.com", hashed_password=hash_password(PASSWORD), role="admin", clinic_id=sur.id))
    db.commit()
    return {
        "norte": norte.id,
        "sur": sur.id,
        "headers": {role: auth_headers(client, f"{role}@norte-ajustes.com") for role in ROLES},
        "sur_admin": auth_headers(client, "admin@sur-ajustes.com"),
    }


def admin(clinics):
    return clinics["headers"]["admin"]


@pytest.mark.parametrize("role", ROLES)
def test_every_role_sees_own_clinic(client, clinics, role):
    response = client.get("/clinic", headers=clinics["headers"][role])

    assert response.status_code == 200
    assert response.json() == {
        "id": clinics["norte"],
        "name": "Clínica Norte",
        "address": "Zona 1",
        "phone": "2222-0000",
        "email": "norte@clinica.com",
        "timezone": "America/Guatemala",
    }


def test_each_admin_sees_only_their_clinic(client, clinics):
    assert client.get("/clinic", headers=clinics["sur_admin"]).json()["name"] == "Clínica Sur"


@pytest.mark.auth
def test_requires_authentication(client):
    assert client.get("/clinic").status_code == 401
    assert client.patch("/clinic", json={"name": "X"}).status_code == 401


@pytest.mark.rbac
@pytest.mark.parametrize("role,expected", [("admin", 200), ("doctor", 403), ("receptionist", 403)])
def test_only_admin_edits(client, clinics, role, expected):
    response = client.patch("/clinic", json={"phone": "2222-9999"}, headers=clinics["headers"][role])

    assert response.status_code == expected


def test_partial_update(client, clinics):
    response = client.patch("/clinic", json={"name": "  Clínica Norte Centro  ", "phone": "2222-1111"}, headers=admin(clinics))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Clínica Norte Centro"
    assert body["phone"] == "2222-1111"
    assert body["address"] == "Zona 1"


def test_new_name_shows_in_me(client, clinics):
    client.patch("/clinic", json={"name": "Clínica Renombrada"}, headers=admin(clinics))

    assert client.get("/auth/me", headers=clinics["headers"]["doctor"]).json()["clinic"]["name"] == "Clínica Renombrada"


def test_empty_optional_fields_are_cleared(client, clinics):
    body = client.patch("/clinic", json={"address": "", "email": None}, headers=admin(clinics)).json()

    assert body["address"] is None
    assert body["email"] is None


def test_cannot_change_other_clinic(client, clinics, db):
    response = client.patch("/clinic", json={"id": clinics["sur"], "name": "Hackeada"}, headers=admin(clinics))

    assert response.status_code == 200
    assert response.json()["id"] == clinics["norte"]
    db.expire_all()
    assert db.get(Clinic, clinics["sur"]).name == "Clínica Sur"


@pytest.mark.parametrize(
    "payload,field",
    [({"name": ""}, "name"), ({"name": "x" * 121}, "name"), ({"email": "no-es-correo"}, "email"), ({"phone": "1" * 31}, "phone")],
)
def test_rejects_invalid_data(client, clinics, payload, field):
    response = client.patch("/clinic", json=payload, headers=admin(clinics))

    assert response.status_code == 422
    assert field in {error["field"] for error in response.json()["errors"]}


def test_name_cannot_be_null(client, clinics):
    response = client.patch("/clinic", json={"name": None}, headers=admin(clinics))

    assert response.status_code == 422
    assert response.json()["detail"] == "El nombre de la clínica es obligatorio."


# --- Zona horaria (ODON-142) ---------------------------------------------------------

def test_admin_changes_timezone(client, clinics):
    response = client.patch("/clinic", json={"timezone": "America/Mexico_City"}, headers=clinics["headers"]["admin"])

    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Mexico_City"


@pytest.mark.parametrize(
    ("value", "message"),
    [("Marte/Olympus", "Zona horaria no válida."), ("", "Campo obligatorio.")],
)
def test_invalid_timezone_is_422(client, clinics, value, message):
    response = client.patch("/clinic", json={"timezone": value}, headers=clinics["headers"]["admin"])

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == message


def test_timezone_cannot_be_removed(client, clinics):
    response = client.patch("/clinic", json={"timezone": None}, headers=clinics["headers"]["admin"])

    assert response.status_code == 422
    assert response.json()["detail"] == "La zona horaria de la clínica es obligatoria."
