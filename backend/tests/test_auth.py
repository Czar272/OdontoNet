"""Login (ODON-38) y usuario actual /auth/me (ODON-42)."""
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth.jwt_handler import ALGORITHM, SECRET_KEY, decode_token
from app.auth.security import verify_password
from app.models import User
from tests.conftest import PASSWORD, create_clinic_with_doctor


def login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


# --- Login --------------------------------------------------------------------

def test_valid_credentials_return_token(client, db):
    _, user, _ = create_clinic_with_doctor(db, "Clinica Login", "login@clinica.com")

    response = login(client, "login@clinica.com")

    assert response.status_code == 200
    payload = decode_token(response.json()["access_token"])
    assert payload["sub"] == "login@clinica.com"
    assert "exp" in payload


def test_wrong_password_and_unknown_email_get_same_401(client, db):
    create_clinic_with_doctor(db, "Clinica Login", "login@clinica.com")

    wrong_password = login(client, "login@clinica.com", "otra-clave")
    unknown_email = login(client, "nadie@clinica.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    # Mismo mensaje: no revela si la cuenta existe.
    assert wrong_password.json() == unknown_email.json() == {"detail": "Credenciales inválidas."}


def test_passwords_are_stored_with_bcrypt(db):
    _, user, _ = create_clinic_with_doctor(db, "Clinica Hash", "hash@clinica.com")
    stored = db.query(User).filter(User.id == user.id).one().hashed_password

    assert stored != PASSWORD
    assert stored.startswith("$2b$")
    assert verify_password(PASSWORD, stored)
    assert not verify_password("otra-clave", stored)


def test_token_does_not_contain_password(client, db):
    create_clinic_with_doctor(db, "Clinica Token", "token@clinica.com")
    payload = decode_token(login(client, "token@clinica.com").json()["access_token"])
    assert PASSWORD not in str(payload)
    assert set(payload) <= {"sub", "role", "exp"}


# --- /auth/me -----------------------------------------------------------------

def test_me_returns_user_and_clinic_without_sensitive_fields(client, db):
    clinic, user, _ = create_clinic_with_doctor(db, "Clinica Me", "me@clinica.com")
    token = login(client, "me@clinica.com").json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": user.id,
        "name": user.name,
        "email": "me@clinica.com",
        "role": "doctor",
        "clinic": {"id": clinic.id, "name": "Clinica Me"},
    }
    assert "password" not in response.text and "hashed" not in response.text


def test_me_rejects_expired_token(client, db):
    create_clinic_with_doctor(db, "Clinica Exp", "exp@clinica.com")
    expired = jwt.encode(
        {"sub": "exp@clinica.com", "role": "doctor", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Token inválido o expirado."}


def test_me_rejects_token_signed_with_other_key(client, db):
    create_clinic_with_doctor(db, "Clinica Firma", "firma@clinica.com")
    forged = jwt.encode(
        {"sub": "firma@clinica.com", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "otra-clave-secreta",
        algorithm=ALGORITHM,
    )

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_me_rejects_malformed_and_missing_token(client):
    assert client.get("/auth/me", headers={"Authorization": "Bearer no.es.jwt"}).status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_deactivated_user(client, db):
    _, user, _ = create_clinic_with_doctor(db, "Clinica Inactiva", "inactiva@clinica.com")
    token = login(client, "inactiva@clinica.com").json()["access_token"]
    db.query(User).filter(User.id == user.id).update({"is_active": False})
    db.commit()

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
