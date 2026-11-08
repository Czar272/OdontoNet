"""Recuperación y cambio de contraseña (ODON-54)."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import jwt

from app.auth import jwt_handler
from app.auth.security import hash_password
from app.models import PasswordResetToken, User
from app.services import email_service, password_service
from tests.conftest import PASSWORD, create_clinic_with_doctor

pytestmark = [pytest.mark.auth]

EMAIL = "olvido@clinica-clave.com"
NEW_PASSWORD = "Nueva-Clave-456"
GENERIC = "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."


@pytest.fixture
def user(db):
    _, user, _ = create_clinic_with_doctor(db, "Clinica Clave", EMAIL)
    return user


@pytest.fixture
def outbox(monkeypatch):
    """Correos enviados durante la prueba (sin SMTP ni log)."""
    sent = []
    monkeypatch.setattr(email_service, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def request_reset(client, email=EMAIL):
    return client.post("/auth/password-reset/request", json={"email": email})


def token_from(outbox) -> str:
    link = next(line for line in outbox[-1][2].splitlines() if "reset-password?token=" in line)
    return parse_qs(urlparse(link.strip()).query)["token"][0]


def confirm(client, token, password=NEW_PASSWORD):
    return client.post("/auth/password-reset/confirm", json={"token": token, "new_password": password})


def login(client, password, email=EMAIL, **extra):
    return client.post("/auth/login", json={"email": email, "password": password, **extra})


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Solicitud ---------------------------------------------------------------


def test_request_sends_link_to_registered_user(client, user, outbox, db):
    response = request_reset(client)

    assert response.status_code == 202
    assert response.json() == {"message": GENERIC}
    assert len(outbox) == 1
    to, subject, body = outbox[0]
    assert to == EMAIL
    assert "contraseña" in subject
    assert "http://localhost:5173/reset-password?token=" in body
    assert db.query(PasswordResetToken).count() == 1


def test_unknown_email_gets_same_response_and_no_mail(client, user, outbox, db):
    response = request_reset(client, "nadie@clinica-clave.com")

    assert response.status_code == 202
    assert response.json() == {"message": GENERIC}
    assert outbox == []
    assert db.query(PasswordResetToken).count() == 0


@pytest.mark.users
def test_inactive_user_gets_same_response_and_no_mail(client, db, outbox):
    create_clinic_with_doctor(db, "Clinica Inactiva", "inactivo@clinica-clave.com", active=False)

    response = request_reset(client, "inactivo@clinica-clave.com")

    assert response.json() == {"message": GENERIC}
    assert outbox == []


def test_invalid_email_is_422(client):
    response = request_reset(client, "no-es-correo")

    assert response.status_code == 422


def test_only_hash_is_stored(client, user, outbox, db):
    request_reset(client)
    token = token_from(outbox)
    stored = db.query(PasswordResetToken).one()

    assert stored.token_hash != token
    assert stored.token_hash == password_service.hash_reset_token(token)
    assert len(token) >= 40


def test_link_expires_after_configured_minutes(client, user, outbox, db):
    before = datetime.now(timezone.utc)
    request_reset(client)
    stored = db.query(PasswordResetToken).one()

    expected = before + timedelta(minutes=password_service.reset_expire_minutes())
    assert abs((stored.expires_at - expected).total_seconds()) < 30


def test_requests_are_limited_per_hour(client, user, outbox):
    for _ in range(password_service.reset_max_per_hour() + 2):
        assert request_reset(client).json() == {"message": GENERIC}

    assert len(outbox) == password_service.reset_max_per_hour()


def test_new_request_invalidates_previous_link(client, user, outbox):
    request_reset(client)
    first = token_from(outbox)
    request_reset(client)
    second = token_from(outbox)

    assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 200


# --- Confirmación ------------------------------------------------------------


def test_reset_changes_password(client, user, outbox):
    request_reset(client)

    response = confirm(client, token_from(outbox))

    assert response.status_code == 200
    assert "actualizó" in response.json()["message"]
    assert login(client, NEW_PASSWORD).status_code == 200
    assert login(client, PASSWORD).status_code == 401


def test_link_works_only_once(client, user, outbox):
    request_reset(client)
    token = token_from(outbox)
    assert confirm(client, token).status_code == 200

    response = confirm(client, token, "Otra-Clave-789")

    assert response.status_code == 400
    assert response.json() == {"detail": password_service.INVALID_LINK}
    assert login(client, NEW_PASSWORD).status_code == 200


def test_expired_link_is_rejected(client, user, outbox, db):
    request_reset(client)
    db.query(PasswordResetToken).update({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    db.commit()

    response = confirm(client, token_from(outbox))

    assert response.status_code == 400
    assert response.json() == {"detail": password_service.INVALID_LINK}
    assert login(client, PASSWORD).status_code == 200


def test_unknown_token_is_rejected_with_same_message(client, user):
    response = confirm(client, "token-inventado")

    assert response.status_code == 400
    assert response.json() == {"detail": password_service.INVALID_LINK}


@pytest.mark.users
def test_link_of_deactivated_user_is_rejected(client, user, outbox, db):
    request_reset(client)
    db.query(User).filter(User.id == user.id).update({"is_active": False})
    db.commit()

    assert confirm(client, token_from(outbox)).status_code == 400


def test_new_password_is_validated(client, user, outbox):
    request_reset(client)

    response = confirm(client, token_from(outbox), "corta")

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "new_password"


def test_reset_closes_open_sessions(client, user, outbox):
    old_token = login(client, PASSWORD, remember_me=True).json()["access_token"]
    assert client.get("/auth/me", headers=bearer(old_token)).status_code == 200

    request_reset(client)
    confirm(client, token_from(outbox))

    response = client.get("/auth/me", headers=bearer(old_token))
    assert response.status_code == 401
    assert response.json() == {"detail": "Tu contraseña cambió. Inicia sesión de nuevo."}
    new_token = login(client, NEW_PASSWORD).json()["access_token"]
    assert client.get("/auth/me", headers=bearer(new_token)).status_code == 200


def test_token_without_iat_is_rejected_after_password_change(client, user, outbox):
    request_reset(client)
    confirm(client, token_from(outbox))
    legacy = jwt.encode(
        {"sub": EMAIL, "role": "doctor", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        jwt_handler.SECRET_KEY,
        algorithm=jwt_handler.ALGORITHM,
    )

    assert client.get("/auth/me", headers=bearer(legacy)).status_code == 401


def test_token_without_iat_still_works_if_password_never_changed(client, user):
    legacy = jwt.encode(
        {"sub": EMAIL, "role": "doctor", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        jwt_handler.SECRET_KEY,
        algorithm=jwt_handler.ALGORITHM,
    )

    assert client.get("/auth/me", headers=bearer(legacy)).status_code == 200


# --- Cambio con sesión iniciada ----------------------------------------------


def change(client, token, current=PASSWORD, new=NEW_PASSWORD, **extra):
    return client.post(
        "/auth/change-password",
        json={"current_password": current, "new_password": new, **extra},
        headers=bearer(token),
    )


def test_change_password_requires_session(client):
    response = client.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 401


def test_change_password_keeps_current_session_and_closes_others(client, user):
    other_session = login(client, PASSWORD).json()["access_token"]
    this_session = login(client, PASSWORD).json()["access_token"]

    response = change(client, this_session)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert client.get("/auth/me", headers=bearer(body["access_token"])).status_code == 200
    assert client.get("/auth/me", headers=bearer(other_session)).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200
    assert login(client, PASSWORD).status_code == 401


def test_change_password_keeps_remember_me_lifetime(client, user):
    token = login(client, PASSWORD, remember_me=True).json()["access_token"]

    body = change(client, token, remember_me=True).json()

    assert body["expires_in"] == jwt_handler.REMEMBER_ME_EXPIRE_DAYS * 24 * 3600


def test_change_password_rejects_wrong_current_password(client, user):
    token = login(client, PASSWORD).json()["access_token"]

    response = change(client, token, current="incorrecta")

    assert response.status_code == 400
    assert response.json() == {"detail": "La contraseña actual no es correcta."}
    # Un error de contraseña actual no cierra la sesión.
    assert client.get("/auth/me", headers=bearer(token)).status_code == 200


def test_change_password_rejects_same_password(client, user):
    token = login(client, PASSWORD).json()["access_token"]

    response = change(client, token, new=PASSWORD)

    assert response.status_code == 400
    assert response.json() == {"detail": "La nueva contraseña debe ser distinta de la actual."}


def test_change_password_validates_new_password(client, user):
    token = login(client, PASSWORD).json()["access_token"]

    response = change(client, token, new="corta")

    assert response.status_code == 422


def test_change_password_invalidates_pending_reset_links(client, user, outbox):
    request_reset(client)
    reset_token = token_from(outbox)
    session = login(client, PASSWORD).json()["access_token"]

    change(client, session)

    assert confirm(client, reset_token, "Otra-Clave-789").status_code == 400


# --- Restablecimiento por administración --------------------------------------


@pytest.mark.users
def test_admin_reset_closes_sessions_of_that_user(client, db, user, outbox):
    db.add(
        User(
            name="Admin Clave",
            email="admin@clinica-clave.com",
            hashed_password=hash_password(PASSWORD),
            role="admin",
            clinic_id=user.clinic_id,
        )
    )
    db.commit()
    request_reset(client)
    pending_link = token_from(outbox)
    user_session = login(client, PASSWORD).json()["access_token"]
    admin_session = login(client, PASSWORD, email="admin@clinica-clave.com").json()["access_token"]

    response = client.patch(f"/users/{user.id}", json={"password": NEW_PASSWORD}, headers=bearer(admin_session))

    assert response.status_code == 200
    assert client.get("/auth/me", headers=bearer(user_session)).status_code == 401
    assert confirm(client, pending_link, "Otra-Clave-789").status_code == 400
    assert login(client, NEW_PASSWORD).status_code == 200


@pytest.mark.users
def test_admin_cannot_set_own_password_through_users(client, db):
    _, admin, _ = create_clinic_with_doctor(db, "Clinica Clave Admin", "admin@clinica-clave.com", role="admin")
    session = login(client, PASSWORD, email="admin@clinica-clave.com").json()["access_token"]

    response = client.patch(f"/users/{admin.id}", json={"password": NEW_PASSWORD}, headers=bearer(session))

    assert response.status_code == 409
    assert response.json() == {"detail": "Para cambiar tu propia contraseña usa «Cambiar contraseña»."}
    assert login(client, PASSWORD, email="admin@clinica-clave.com").status_code == 200


# --- Servicio de correo -------------------------------------------------------


class FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.calls = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, message):
        self.calls.append(("send", message["To"], message["Subject"]))


def test_email_without_smtp_goes_to_log(monkeypatch, caplog):
    monkeypatch.delenv("SMTP_HOST", raising=False)

    with caplog.at_level("INFO", logger="odontonet.email"):
        email_service.send_email("a@clinica.com", "Asunto", "enlace-de-prueba")

    assert "enlace-de-prueba" in caplog.text


def test_email_with_smtp_uses_starttls_and_login(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.com")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USER", "usuario")
    monkeypatch.setenv("SMTP_PASSWORD", "secreto")

    email_service.send_email("a@clinica.com", "Asunto", "Cuerpo")

    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.ejemplo.com", 2525)
    assert smtp.calls == ["starttls", ("login", "usuario"), ("send", "a@clinica.com", "Asunto")]


def test_smtp_failure_is_logged_without_body(monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise OSError("sin conexión")

    monkeypatch.setattr(email_service.smtplib, "SMTP", broken)
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.com")

    with caplog.at_level("ERROR", logger="odontonet.email"):
        email_service.send_email("a@clinica.com", "Asunto", "enlace-secreto")

    assert "No se pudo enviar" in caplog.text
    assert "enlace-secreto" not in caplog.text
