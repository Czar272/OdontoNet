"""Gestión de usuarios por administración (ODON-86 / ODON-89)."""
import pytest

from app.auth.security import hash_password
from app.models import Clinic, Doctor, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.users]

ROLES = ("admin", "doctor", "receptionist")
NEW_PASSWORD = "Nueva-Clave-123"


@pytest.fixture
def staff(db, client):
    """Clínica Norte con un usuario por rol (el doctor con perfil clínico),
    un recepcionista extra y una Clínica Sur con su propio administrador."""
    norte = Clinic(name="Clinica Norte")
    sur = Clinic(name="Clinica Sur")
    db.add_all([norte, sur])
    db.flush()

    def add_user(clinic, email, role, name=None):
        user = User(
            name=name or f"Usuario {email}",
            email=email,
            hashed_password=hash_password(PASSWORD),
            role=role,
            clinic_id=clinic.id,
        )
        db.add(user)
        db.flush()
        return user

    users = {role: add_user(norte, f"{role}@norte-clinica.com", role) for role in ROLES}
    extra = add_user(norte, "extra@norte-clinica.com", "receptionist", name="Ana Extra")
    sur_admin = add_user(sur, "admin@sur-clinica.com", "admin")
    db.add(Doctor(user_id=users["doctor"].id, clinic_id=norte.id))
    db.commit()

    return {
        "clinic": norte.id,
        "ids": {**{role: user.id for role, user in users.items()}, "extra": extra.id, "sur_admin": sur_admin.id},
        "headers": {role: auth_headers(client, f"{role}@norte-clinica.com") for role in ROLES},
    }


def admin(staff):
    return staff["headers"]["admin"]


# --- Autorización -----------------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/users/", None),
        ("get", "/users/{extra}", None),
        ("post", "/users/", {"name": "Nuevo", "email": "nuevo.{role}@norte-clinica.com", "password": NEW_PASSWORD}),
        ("patch", "/users/{extra}", {"name": "Editado"}),
    ],
)
def test_only_admin_manages_users(client, staff, role, method, path, body):
    url = path.format(extra=staff["ids"]["extra"])
    kwargs = {}
    if body:
        kwargs["json"] = {k: (v.format(role=role) if isinstance(v, str) else v) for k, v in body.items()}

    response = getattr(client, method)(url, headers=staff["headers"][role], **kwargs)

    if role == "admin":
        assert response.status_code in (200, 201), response.text
    else:
        assert response.status_code == 403


@pytest.mark.auth
@pytest.mark.parametrize("method", ["get", "post"])
def test_users_require_authentication(client, method):
    assert getattr(client, method)("/users/").status_code == 401


# --- Listado y consulta -----------------------------------------------------

@pytest.mark.isolation
def test_list_only_shows_own_clinic(client, staff):
    response = client.get("/users/", headers=admin(staff))

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert emails == {"admin@norte-clinica.com", "doctor@norte-clinica.com", "receptionist@norte-clinica.com", "extra@norte-clinica.com"}
    assert all(user["clinic_id"] == staff["clinic"] for user in response.json())


def test_list_filters_by_role(client, staff):
    response = client.get("/users/", params={"role": "receptionist"}, headers=admin(staff))

    assert response.status_code == 200
    assert {user["role"] for user in response.json()} == {"receptionist"}
    assert len(response.json()) == 2


def test_list_rejects_unknown_role(client, staff):
    assert client.get("/users/", params={"role": "superadmin"}, headers=admin(staff)).status_code == 422


def test_responses_never_expose_passwords(client, staff):
    listed = client.get("/users/", headers=admin(staff)).json()
    single = client.get(f"/users/{staff['ids']['extra']}", headers=admin(staff)).json()

    for user in [*listed, single]:
        assert set(user) == {"id", "name", "email", "role", "clinic_id", "is_active"}


@pytest.mark.isolation
def test_user_from_other_clinic_is_not_found(client, staff):
    sur_id = staff["ids"]["sur_admin"]

    assert client.get(f"/users/{sur_id}", headers=admin(staff)).status_code == 404
    assert client.patch(f"/users/{sur_id}", json={"name": "Hack"}, headers=admin(staff)).status_code == 404


# --- Alta ---------------------------------------------------------------------

@pytest.mark.isolation
def test_create_assigns_admin_clinic_and_ignores_clinic_id(client, staff):
    payload = {"name": "Recep Nueva", "email": "recep.nueva@norte-clinica.com", "password": NEW_PASSWORD, "role": "receptionist", "clinic_id": 999}

    response = client.post("/users/", json=payload, headers=admin(staff))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["clinic_id"] == staff["clinic"]
    assert body["role"] == "receptionist"
    assert body["is_active"] is True
    assert client.post("/auth/login", json={"email": payload["email"], "password": NEW_PASSWORD}).status_code == 200


def test_create_defaults_to_doctor_role(client, staff):
    payload = {"name": "Dra. Nueva", "email": "dra.nueva@norte-clinica.com", "password": NEW_PASSWORD}

    assert client.post("/users/", json=payload, headers=admin(staff)).json()["role"] == "doctor"


def test_create_duplicate_email_conflicts_across_clinics(client, staff):
    payload = {"name": "Dup", "email": "admin@sur-clinica.com", "password": NEW_PASSWORD}

    response = client.post("/users/", json=payload, headers=admin(staff))

    assert response.status_code == 409
    assert response.json()["detail"] == "Ya existe un usuario con ese correo."


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"name": "X", "email": "x1@norte-clinica.com", "password": NEW_PASSWORD, "role": "superadmin"}, "role"),
        ({"name": "X", "email": "x2@norte-clinica.com", "password": "corta"}, "password"),
        ({"name": "  ", "email": "x3@norte-clinica.com", "password": NEW_PASSWORD}, "name"),
        ({"name": "X", "email": "no-es-correo", "password": NEW_PASSWORD}, "email"),
    ],
)
def test_create_rejects_invalid_data(client, staff, payload, field):
    response = client.post("/users/", json=payload, headers=admin(staff))

    assert response.status_code == 422
    assert field in {error["field"] for error in response.json()["errors"]}


# --- Edición ------------------------------------------------------------------

def test_update_name_email_and_role(client, staff):
    extra = staff["ids"]["extra"]

    response = client.patch(
        f"/users/{extra}",
        json={"name": "Ana Editada", "email": "ana.editada@norte-clinica.com", "role": "admin"},
        headers=admin(staff),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["email"], body["role"]) == ("Ana Editada", "ana.editada@norte-clinica.com", "admin")
    assert client.post("/auth/login", json={"email": "ana.editada@norte-clinica.com", "password": PASSWORD}).status_code == 200


def test_partial_update_keeps_other_fields(client, staff):
    extra = staff["ids"]["extra"]

    body = client.patch(f"/users/{extra}", json={"name": "Solo Nombre", "email": None}, headers=admin(staff)).json()

    assert body["name"] == "Solo Nombre"
    assert body["email"] == "extra@norte-clinica.com"
    assert body["role"] == "receptionist"


def test_password_reset_replaces_old_password(client, staff):
    extra = staff["ids"]["extra"]

    response = client.patch(f"/users/{extra}", json={"password": NEW_PASSWORD}, headers=admin(staff))

    assert response.status_code == 200
    assert "password" not in response.json()
    assert client.post("/auth/login", json={"email": "extra@norte-clinica.com", "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": "extra@norte-clinica.com", "password": NEW_PASSWORD}).status_code == 200


def test_update_rejects_email_of_another_user(client, staff):
    response = client.patch(f"/users/{staff['ids']['extra']}", json={"email": "doctor@norte-clinica.com"}, headers=admin(staff))

    assert response.status_code == 409


def test_update_keeping_same_email_is_allowed(client, staff):
    response = client.patch(f"/users/{staff['ids']['extra']}", json={"email": "extra@norte-clinica.com"}, headers=admin(staff))

    assert response.status_code == 200


@pytest.mark.parametrize("payload", [{"role": "superadmin"}, {"password": "corta"}, {"name": ""}, {"clinic_id": 999, "name": ""}])
def test_update_rejects_invalid_data(client, staff, payload):
    response = client.patch(f"/users/{staff['ids']['extra']}", json=payload, headers=admin(staff))

    assert response.status_code == 422


@pytest.mark.isolation
def test_update_cannot_move_user_to_another_clinic(client, staff):
    extra = staff["ids"]["extra"]

    response = client.patch(f"/users/{extra}", json={"clinic_id": 999, "name": "Sigue aquí"}, headers=admin(staff))

    assert response.status_code == 200
    assert response.json()["clinic_id"] == staff["clinic"]


@pytest.mark.rbac
def test_admin_cannot_change_own_role(client, staff):
    response = client.patch(f"/users/{staff['ids']['admin']}", json={"role": "doctor"}, headers=admin(staff))

    assert response.status_code == 409
    assert response.json()["detail"] == "No puedes cambiar tu propio rol."


def test_admin_can_edit_own_name(client, staff):
    response = client.patch(f"/users/{staff['ids']['admin']}", json={"name": "Admin Renombrado", "role": "admin"}, headers=admin(staff))

    assert response.status_code == 200
    assert response.json()["name"] == "Admin Renombrado"


@pytest.mark.doctors
def test_role_of_user_with_doctor_profile_cannot_change(client, staff):
    response = client.patch(f"/users/{staff['ids']['doctor']}", json={"role": "receptionist"}, headers=admin(staff))

    assert response.status_code == 409
    assert "perfil de doctor" in response.json()["detail"]


@pytest.mark.doctors
def test_user_with_doctor_profile_can_become_admin(client, staff):
    response = client.patch(f"/users/{staff['ids']['doctor']}", json={"role": "admin"}, headers=admin(staff))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.rbac
def test_role_change_applies_to_existing_token(client, staff):
    receptionist_headers = staff["headers"]["receptionist"]
    client.patch(f"/users/{staff['ids']['receptionist']}", json={"role": "admin"}, headers=admin(staff))

    assert client.get("/users/", headers=receptionist_headers).status_code == 200
