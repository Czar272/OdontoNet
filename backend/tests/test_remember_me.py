"""Opción "Recuérdame" en el login (ODON-255)."""
from datetime import datetime, timezone

import pytest

from app.auth.jwt_handler import ACCESS_TOKEN_EXPIRE_MINUTES, decode_token
from app.core.settings import get_settings
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


def test_remember_me_keeps_a_short_access_token_and_a_lasting_cookie(client, user):
    response = login(client, remember_me=True)
    body = response.json()

    assert body["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert abs(lifetime_seconds(body["access_token"]) - body["expires_in"]) < 30
    cookie = response.headers["set-cookie"]
    assert abs(int(cookie.split("Max-Age=")[1].split(";")[0]) - get_settings().remember_me_expire_days * 86400) < 30
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_without_remember_me_the_cookie_ends_with_the_browser(client, user):
    assert "Max-Age" not in login(client).headers["set-cookie"]


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
