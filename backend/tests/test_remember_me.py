"""Opción "Recuérdame" en el login (ODON-255)."""
from datetime import datetime, timezone

import pytest

from app.auth.jwt_handler import ACCESS_TOKEN_EXPIRE_MINUTES, REMEMBER_ME_EXPIRE_DAYS, decode_token
from app.models import User
from tests.conftest import PASSWORD, create_clinic_with_doctor

pytestmark = [pytest.mark.auth]

EMAIL = "recuerdame@clinica-sesion.com"


@pytest.fixture
def user(db):
    create_clinic_with_doctor(db, "Clinica Sesion", EMAIL)


def login(client, **extra):
    return client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD, **extra})


def lifetime_seconds(token: str) -> float:
    exp = decode_token(token)["exp"]
    return exp - datetime.now(timezone.utc).timestamp()


def test_default_session_is_short(client, user):
    body = login(client).json()

    assert body["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert abs(lifetime_seconds(body["access_token"]) - body["expires_in"]) < 30


def test_remember_me_false_is_short(client, user):
    assert login(client, remember_me=False).json()["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_remember_me_gives_long_session(client, user):
    body = login(client, remember_me=True).json()

    assert body["expires_in"] == REMEMBER_ME_EXPIRE_DAYS * 24 * 3600
    assert abs(lifetime_seconds(body["access_token"]) - body["expires_in"]) < 30
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_remember_me_does_not_bypass_wrong_password(client, user):
    response = client.post("/auth/login", json={"email": EMAIL, "password": "incorrecta", "remember_me": True})

    assert response.status_code == 401


@pytest.mark.users
def test_long_token_still_revoked_when_user_is_deactivated(client, user, db):
    token = login(client, remember_me=True).json()["access_token"]
    db.query(User).filter(User.email == EMAIL).update({"is_active": False})
    db.commit()

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_remember_me_rejects_non_boolean(client, user):
    assert login(client, remember_me="tal vez").status_code == 422
