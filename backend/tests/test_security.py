"""Endurecimiento (ODON-230): límite de intentos, política de contraseñas, cabeceras y CORS."""
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.security import hash_password
from app.core.password_policy import check_new_password, common_passwords
from app.main import cors_origins
from app.models import AuthAttempt, User
from app.services import email_service
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.auth]

EMAIL = "limite@clinica-segura.com"


@pytest.fixture
def user(db):
    _, user, _ = create_clinic_with_doctor(db, "Clinica Segura", EMAIL, role="admin")
    return user


@pytest.fixture(autouse=True)
def no_email(monkeypatch):
    monkeypatch.setattr(email_service, "send_email", lambda *args: None)


def login(client, email=EMAIL, password="incorrecta", headers=None):
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers or {})


# --- Límite de inicio de sesión ----------------------------------------------

def test_seventh_failure_locks_the_account_even_with_the_right_password(client, user):
    for _ in range(7):
        assert login(client).status_code == 401
    response = login(client, password=PASSWORD)
    assert response.status_code == 429
    assert response.json()["detail"].startswith("Demasiados intentos. Espera 15 minutos")
    assert 0 < int(response.headers["Retry-After"]) <= 15 * 60


def test_lock_is_per_account(client, db, user):
    create_clinic_with_doctor(db, "Clinica Vecina", "otro@clinica-vecina.com")
    for _ in range(7):
        login(client)
    assert login(client, email="otro@clinica-vecina.com", password=PASSWORD).status_code == 200


def test_unknown_accounts_are_limited_too(client, user):
    # Mismo trato que una cuenta real: el límite no revela qué correos existen.
    for _ in range(7):
        assert login(client, email="nadie@clinica-segura.com").status_code == 401
    assert login(client, email="nadie@clinica-segura.com").status_code == 429


def test_success_clears_previous_failures(client, user):
    for _ in range(6):
        login(client)
    assert login(client, password=PASSWORD).status_code == 200
    for _ in range(6):
        assert login(client).status_code == 401
    assert login(client, password=PASSWORD).status_code == 200


def test_lock_expires_after_fifteen_minutes(client, db, user):
    for _ in range(7):
        login(client)
    assert login(client, password=PASSWORD).status_code == 429
    db.query(AuthAttempt).update({"attempted_at": datetime.now(timezone.utc) - timedelta(minutes=16)})
    db.commit()
    assert login(client, password=PASSWORD).status_code == 200


def test_lock_lasts_fifteen_minutes_from_the_seventh_failure(client, db, user):
    # 7 fallos de t=0 a t=6 min; ahora es t=16: el primero ya salió de la ventana
    # de 15 minutos, pero el bloqueo sigue hasta t=21 (15 desde el séptimo).
    for _ in range(7):
        login(client)
    now = datetime.now(timezone.utc)
    for index, attempt in enumerate(db.query(AuthAttempt).order_by(AuthAttempt.id).all()):
        attempt.attempted_at = now - timedelta(minutes=16 - index)
    db.commit()
    response = login(client, password=PASSWORD)
    assert response.status_code == 429
    assert 4 * 60 < int(response.headers["Retry-After"]) <= 5 * 60

    # Pasado t=21 se puede entrar.
    db.query(AuthAttempt).update({"attempted_at": AuthAttempt.attempted_at - timedelta(minutes=6)})
    db.commit()
    assert login(client, password=PASSWORD).status_code == 200


def test_lock_minutes_can_exceed_the_window(client, user, monkeypatch):
    monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "1")
    monkeypatch.setenv("LOGIN_LOCK_MINUTES", "60")
    for _ in range(7):
        login(client)
    response = login(client, password=PASSWORD)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 59 * 60


def test_wrong_current_password_counts_as_a_failure(client, user, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FAILURES_PER_ACCOUNT", "2")
    headers = auth_headers(client, EMAIL)
    body = {"current_password": "no-es-la-actual", "new_password": "Otra-Clave-Larga-9"}
    for _ in range(2):
        assert client.post("/auth/change-password", json=body, headers=headers).status_code == 400
    assert client.post("/auth/change-password", json=body, headers=headers).status_code == 429


def test_ip_limit_across_accounts(client, user, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FAILURES_PER_IP", "3")
    for index in range(3):
        login(client, email=f"usuario{index}@clinica-segura.com")
    response = login(client, password=PASSWORD)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_forwarded_header_ignored_unless_trusted(client, user, monkeypatch):
    monkeypatch.setenv("LOGIN_MAX_FAILURES_PER_IP", "2")
    for index in range(2):
        login(client, email=f"a{index}@clinica-segura.com", headers={"X-Forwarded-For": f"10.0.0.{index}"})
    # Sin proxy de confianza, cambiar la cabecera no evade el límite por IP.
    assert login(client, email="b@clinica-segura.com", headers={"X-Forwarded-For": "10.9.9.9"}).status_code == 429

    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    assert login(client, email="b@clinica-segura.com", headers={"X-Forwarded-For": "10.9.9.9"}).status_code == 401
    # Con proxy de confianza cuenta la última entrada (la que agrega el proxy),
    # no las que el cliente escribe antes.
    for index in range(2):
        login(client, email=f"c{index}@clinica-segura.com", headers={"X-Forwarded-For": f"1.1.1.{index}, 10.8.8.8"})
    assert login(client, email="d@clinica-segura.com", headers={"X-Forwarded-For": "2.2.2.2, 10.8.8.8"}).status_code == 429


def test_attempts_store_no_email_and_old_rows_are_purged(client, db, user):
    db.add(AuthAttempt(kind="login", ip="1.2.3.4", account_key="x" * 64,
                       attempted_at=datetime.now(timezone.utc) - timedelta(days=2)))
    db.commit()
    login(client)
    rows = db.query(AuthAttempt).all()
    assert len(rows) == 1
    assert EMAIL not in rows[0].account_key and len(rows[0].account_key) == 64


# --- Límite de recuperación ---------------------------------------------------

def test_reset_requests_limited_per_ip(client, user, monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_MAX_PER_IP", "2")
    for _ in range(2):
        assert client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
    response = client.post("/auth/password-reset/request", json={"email": "otro@clinica-segura.com"})
    assert response.status_code == 429


def test_invalid_reset_links_limited_per_ip(client, user, monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_CONFIRM_MAX_FAILURES_PER_IP", "2")
    body = {"token": "no-existe", "new_password": "Una-Clave-Larga-1"}
    for _ in range(2):
        assert client.post("/auth/password-reset/confirm", json=body).status_code == 400
    assert client.post("/auth/password-reset/confirm", json=body).status_code == 429


# --- Política de contraseñas --------------------------------------------------

@pytest.mark.users
@pytest.mark.parametrize("password,message", [
    ("Corta-123", "Debe tener al menos 10 caracteres."),
    ("password1234", "Esa contraseña aparece en listas de contraseñas filtradas. Elige otra."),
    ("QWERTYUIOP", "Esa contraseña aparece en listas de contraseñas filtradas. Elige otra."),
])
def test_new_user_password_policy(client, user, password, message):
    headers = auth_headers(client, EMAIL)
    response = client.post("/users/", json={"name": "Nueva", "email": "nueva@clinica-segura.com",
                                             "password": password, "role": "doctor"}, headers=headers)
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "password", "message": message}]


def test_change_password_rejects_common_passwords(client, user):
    headers = auth_headers(client, EMAIL)
    response = client.post("/auth/change-password", headers=headers,
                           json={"current_password": PASSWORD, "new_password": "1234567890"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "new_password"


@pytest.mark.users
def test_admin_reset_of_password_uses_the_policy(client, db, user):
    other = User(name="Recepción", email="recepcion@clinica-segura.com", hashed_password=hash_password(PASSWORD),
                 role="receptionist", clinic_id=user.clinic_id)
    db.add(other)
    db.commit()
    headers = auth_headers(client, EMAIL)
    response = client.patch(f"/users/{other.id}", json={"password": "qwertyuiop"}, headers=headers)
    assert response.status_code == 422


def test_existing_short_passwords_still_log_in(client, db, user):
    # La política se exige en el próximo cambio, no al iniciar sesión.
    db.query(User).filter(User.id == user.id).update({"hashed_password": hash_password("ocho1234")})
    db.commit()
    assert login(client, password="ocho1234").status_code == 200


def test_common_password_list_loaded():
    common = common_passwords()
    assert len(common) > 9000
    assert all(len(word) >= 10 for word in common)
    with pytest.raises(ValueError):
        check_new_password("  Password1234 ")
    assert check_new_password("Una frase larga y propia") == "Una frase larga y propia"


# --- Cabeceras y CORS ---------------------------------------------------------

@pytest.mark.api
def test_security_headers_on_api_responses(client, user):
    response = client.get("/auth/me", headers=auth_headers(client, EMAIL))
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert response.headers["Cache-Control"] == "no-store"
    assert "camera=()" in response.headers["Permissions-Policy"]


@pytest.mark.api
def test_docs_keep_working_without_strict_csp(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.api
def test_cors_allows_only_configured_origins(client):
    allowed = client.options("/auth/login", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    denied = client.options("/auth/login", headers={
        "Origin": "https://sitio-ajeno.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.api
def test_cors_rejects_wildcards():
    assert cors_origins(" http://a.test , ,http://b.test") == ["http://a.test", "http://b.test"]
    with pytest.raises(RuntimeError):
        cors_origins("http://a.test,*")


@pytest.mark.api
def test_unknown_host_header_is_rejected(client):
    # Mitigación de Starlette PYSEC-2026-161 (ODON-263): solo hosts de ALLOWED_HOSTS.
    assert client.get("/health").status_code == 200
    response = client.get("/health", headers={"Host": "sitio-ajeno.example"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Host no permitido."}
    assert client.get("/health", headers={"Host": "LOCALHOST:8000"}).status_code == 200


@pytest.mark.api
def test_allowed_hosts_rejects_wildcards_and_empty_lists():
    from app.core.allowed_hosts import parse_allowed_hosts
    assert parse_allowed_hosts(" localhost , API.clinica.test ") == ["localhost", "api.clinica.test"]
    for raw in ("*", "localhost,*.clinica.test", " , "):
        with pytest.raises(RuntimeError):
            parse_allowed_hosts(raw)


def test_tokens_in_the_previous_library_format_stay_valid(client, user):
    """Un token con el formato de python-jose (cabecera {"alg":"HS256","typ":"JWT"}
    e iat fraccionario), firmado a mano, sigue siendo válido con PyJWT (ODON-263)."""
    import base64
    import hashlib
    import hmac
    import json
    from datetime import datetime, timedelta, timezone

    from app.auth.jwt_handler import SECRET_KEY

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    now = datetime.now(timezone.utc)
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64(json.dumps({"sub": EMAIL, "role": "admin", "exp": int((now + timedelta(minutes=5)).timestamp()),
                              "iat": now.timestamp()}, separators=(",", ":")).encode())
    signature = b64(hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {header}.{payload}.{signature}"})
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
