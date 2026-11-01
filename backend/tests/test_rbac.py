"""Matriz de permisos por rol (ODON-66 / ODON-69). Ver docs/PERMISSIONS.md."""
import pytest

from app.auth.security import hash_password
from app.models import Clinic, Doctor, User
from tests.conftest import PASSWORD, auth_headers

pytestmark = [pytest.mark.rbac]


ROLES = ("admin", "doctor", "receptionist")


@pytest.fixture
def clinic_staff(db, client):
    """Una clínica con un usuario por rol, su doctor y un usuario sin perfil clínico."""
    clinic = Clinic(name="Clinica RBAC")
    db.add(clinic)
    db.flush()

    users = {}
    for role in ROLES:
        user = User(
            name=f"Usuario {role}",
            email=f"{role}@rbac-clinica.com",
            hashed_password=hash_password(PASSWORD),
            role=role,
            clinic_id=clinic.id,
        )
        db.add(user)
        db.flush()
        users[role] = user

    doctor = Doctor(user_id=users["doctor"].id, clinic_id=clinic.id)
    spare = User(
        name="Sin perfil",
        email="spare@rbac-clinica.com",
        hashed_password=hash_password(PASSWORD),
        role="doctor",
        clinic_id=clinic.id,
    )
    db.add_all([doctor, spare])
    db.commit()

    return {
        "clinic": clinic.id,
        "doctor": doctor.id,
        "spare_user": spare.id,
        "headers": {role: auth_headers(client, f"{role}@rbac-clinica.com") for role in ROLES},
    }


# (método, ruta, cuerpo, roles permitidos)
MATRIX = [
    ("get", "/auth/me", None, ROLES),
    ("get", "/patients/", None, ROLES),
    ("post", "/patients/", {"first_name": "Ana", "last_name": "López"}, ROLES),
    ("get", "/doctors/", None, ROLES),
    ("get", "/doctors/{doctor}", None, ROLES),
]


@pytest.mark.patients
@pytest.mark.doctors
@pytest.mark.doctors
@pytest.mark.users
@pytest.mark.users
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("method,path,body,allowed", MATRIX)
def test_shared_endpoints_by_role(client, clinic_staff, role, method, path, body, allowed):
    url = path.format(doctor=clinic_staff["doctor"])
    response = getattr(client, method)(url, headers=clinic_staff["headers"][role], **({"json": body} if body else {}))

    if role in allowed:
        assert response.status_code in (200, 201), response.text
    else:
        assert response.status_code == 403


@pytest.mark.parametrize("role,expected", [("admin", 201), ("doctor", 403), ("receptionist", 403)])
def test_only_admin_creates_doctor_profiles(client, clinic_staff, role, expected):
    response = client.post(
        "/doctors/",
        json={"user_id": clinic_staff["spare_user"]},
        headers=clinic_staff["headers"][role],
    )
    assert response.status_code == expected, response.text


@pytest.mark.parametrize("role,expected", [("admin", 201), ("doctor", 403), ("receptionist", 403)])
def test_only_admin_registers_users(client, clinic_staff, role, expected):
    payload = {"name": "Nueva", "email": f"nueva.{role}@rbac-clinica.com", "password": "Segura-123", "role": "receptionist"}
    response = client.post("/auth/register", json=payload, headers=clinic_staff["headers"][role])
    assert response.status_code == expected, response.text


@pytest.mark.users
@pytest.mark.auth
def test_register_requires_authentication(client):
    payload = {"name": "X", "email": "x@rbac-clinica.com", "password": "Segura-123"}
    assert client.post("/auth/register", json=payload).status_code in (401, 403)


@pytest.mark.users
@pytest.mark.isolation
def test_registered_user_belongs_to_admin_clinic(client, clinic_staff):
    payload = {"name": "Recep", "email": "recep2@rbac-clinica.com", "password": "Segura-123", "role": "receptionist", "clinic_id": 999}

    response = client.post("/auth/register", json=payload, headers=clinic_staff["headers"]["admin"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["clinic_id"] == clinic_staff["clinic"]
    assert body["role"] == "receptionist"
    assert "password" not in body and "hashed_password" not in body
    assert client.post("/auth/login", json={"email": "recep2@rbac-clinica.com", "password": "Segura-123"}).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "X", "email": "x1@rbac-clinica.com", "password": "Segura-123", "role": "superadmin"},
        {"name": "X", "email": "x2@rbac-clinica.com", "password": "corta"},
        {"name": " ", "email": "x3@rbac-clinica.com", "password": "Segura-123"},
    ],
)
def test_register_rejects_invalid_data(client, clinic_staff, payload):
    response = client.post("/auth/register", json=payload, headers=clinic_staff["headers"]["admin"])
    assert response.status_code == 422


@pytest.mark.users
def test_register_duplicate_email_conflicts(client, clinic_staff):
    payload = {"name": "Dup", "email": "doctor@rbac-clinica.com", "password": "Segura-123"}
    response = client.post("/auth/register", json=payload, headers=clinic_staff["headers"]["admin"])
    assert response.status_code == 409


@pytest.mark.auth
def test_unknown_role_in_database_is_denied(client, db, clinic_staff):
    user = User(
        name="Rol raro",
        email="raro@rbac-clinica.com",
        hashed_password=hash_password(PASSWORD),
        role="intern",
        clinic_id=clinic_staff["clinic"],
    )
    db.add(user)
    db.commit()

    headers = auth_headers(client, "raro@rbac-clinica.com")

    assert client.get("/patients/", headers=headers).status_code == 403


@pytest.mark.auth
def test_role_change_takes_effect_without_new_token(client, db, clinic_staff):
    headers = clinic_staff["headers"]["admin"]
    admin = db.query(User).filter(User.email == "admin@rbac-clinica.com").one()
    admin.role = "receptionist"
    db.commit()

    response = client.post("/doctors/", json={"user_id": clinic_staff["spare_user"]}, headers=headers)

    assert response.status_code == 403


@pytest.mark.auth
def test_inactive_user_cannot_log_in(client, db, clinic_staff):
    user = db.query(User).filter(User.email == "doctor@rbac-clinica.com").one()
    user.is_active = False
    db.commit()

    response = client.post("/auth/login", json={"email": "doctor@rbac-clinica.com", "password": PASSWORD})

    assert response.status_code == 401
