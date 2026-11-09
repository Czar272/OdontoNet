"""Sesión con refresh token rotativo en cookie httpOnly (ODON-265)."""
from datetime import datetime, timedelta, timezone

import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import decode_token
from app.database.connection import SessionLocal
from app.main import app
from app.models import AuthSession
from app.services import session_service
from tests.conftest import PASSWORD, create_clinic_with_doctor

pytestmark = pytest.mark.auth

ORIGIN = {"Origin": "http://localhost:5173"}
COOKIE = "odontonet_session"
EMAIL = "sesion@clinica-uno.com"
NEW_PASSWORD = "Otra-Password-456"


@pytest.fixture
def account(db):
    return create_clinic_with_doctor(db, "Clinica Uno", EMAIL)


def login(client, email=EMAIL, **extra):
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD, **extra})
    assert response.status_code == 200, response.text
    return response


def refresh(client):
    return client.post("/auth/refresh", headers=ORIGIN)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def age_last_use(db, seconds):
    """Simula que el último uso de los tokens ocurrió hace `seconds` segundos."""
    past = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    db.query(AuthSession).filter(AuthSession.used_at.isnot(None)).update({"used_at": past})
    db.commit()


def test_login_sets_a_protected_cookie_without_exposing_the_token(client, account):
    response = login(client)
    cookie = response.headers["set-cookie"].lower()
    assert all(flag in cookie for flag in ("httponly", "samesite=strict", "path=/auth"))
    assert client.cookies[COOKIE] not in response.text


def test_only_the_hash_is_stored(client, account, db):
    login(client)
    row = db.query(AuthSession).one()
    assert row.token_hash != client.cookies[COOKIE] and len(row.token_hash) == 64


def test_cookie_is_secure_in_production(monkeypatch, client, account):
    monkeypatch.setenv("APP_ENV", "production")
    assert "secure" in login(client).headers["set-cookie"].lower()


def test_refresh_rotates_the_cookie_and_gives_a_working_token(client, account, db):
    login(client)
    before = client.cookies[COOKIE]
    response = refresh(client)
    assert response.status_code == 200, response.text
    assert client.cookies[COOKIE] != before
    assert client.get("/auth/me", headers=bearer(response.json()["access_token"])).status_code == 200
    rows = db.query(AuthSession).order_by(AuthSession.id).all()
    assert len(rows) == 2 and rows[0].used_at is not None and rows[0].family_id == rows[1].family_id


def test_renewing_does_not_extend_the_session(client, account, db):
    login(client)
    refresh(client)
    rows = db.query(AuthSession).all()
    assert rows[0].expires_at == rows[1].expires_at


def test_refresh_without_cookie_is_unauthorized(client):
    assert refresh(client).status_code == 401


def test_refresh_with_unknown_cookie_clears_it(client):
    client.cookies.set(COOKIE, "desconocida", path="/auth")
    response = refresh(client)
    assert response.status_code == 401
    assert response.json() == {"detail": "La sesión expiró."}
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_expired_session_cannot_be_renewed(client, account, db):
    login(client)
    db.query(AuthSession).update({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    db.commit()
    assert refresh(client).status_code == 401


def test_concurrent_reuse_within_grace_gets_a_token_without_rotating(client, account, db):
    login(client)
    old = client.cookies[COOKIE]
    refresh(client)
    client.cookies.clear()
    client.cookies.set(COOKIE, old, path="/auth")
    response = refresh(client)
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert db.query(AuthSession).count() == 2


def test_reuse_after_grace_revokes_the_family(client, account, db, caplog):
    login(client)
    old = client.cookies[COOKIE]
    refresh(client)
    newest = client.cookies[COOKIE]
    access = login(client, remember_me=False)  # otra sesión del mismo usuario no se afecta
    other = client.cookies[COOKIE]
    age_last_use(db, 60)

    client.cookies.clear()
    client.cookies.set(COOKIE, old, path="/auth")
    with caplog.at_level("WARNING", logger="odontonet.audit"):
        assert refresh(client).status_code == 401
    assert any("auth.session_reuse_detected" in record.getMessage() for record in caplog.records)
    assert EMAIL not in caplog.text

    client.cookies.clear()
    client.cookies.set(COOKIE, newest, path="/auth")
    assert refresh(client).status_code == 401

    client.cookies.clear()
    client.cookies.set(COOKIE, other, path="/auth")
    assert refresh(client).status_code == 200
    assert access.status_code == 200


def test_logout_revokes_refresh_and_access_token(client, account):
    token = login(client).json()["access_token"]
    cookie = client.cookies[COOKIE]
    response = client.post("/auth/logout", headers=ORIGIN)
    assert response.status_code == 200
    assert "max-age=0" in response.headers["set-cookie"].lower()

    assert client.get("/auth/me", headers=bearer(token)).status_code == 401
    client.cookies.set(COOKIE, cookie, path="/auth")
    assert refresh(client).status_code == 401


def test_logout_without_session_is_harmless(client):
    assert client.post("/auth/logout", headers=ORIGIN).status_code == 200


def test_access_token_carries_the_session_id(client, account, db):
    token = login(client).json()["access_token"]
    assert decode_token(token)["sid"] == db.query(AuthSession).one().family_id


@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout"])
@pytest.mark.parametrize("headers", [{}, {"Origin": "https://sitio-ajeno.test"}, {"Origin": "null"}])
def test_cookie_routes_reject_foreign_or_missing_origin(client, account, path, headers):
    login(client)
    assert client.post(path, headers=headers).status_code == 403


def test_configured_cors_origin_is_accepted(monkeypatch, client, account):
    monkeypatch.setenv("CORS_ORIGINS", "https://otra.clinica.test")
    login(client)
    assert client.post("/auth/refresh", headers={"Origin": "https://otra.clinica.test"}).status_code == 200


def test_changing_password_revokes_other_sessions_and_keeps_this_one(client, account):
    other = TestClient(app)
    login(other)
    response = login(client, remember_me=True)
    change = client.post("/auth/change-password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD,
    }, headers=bearer(response.json()["access_token"]))
    assert change.status_code == 200, change.text
    assert "max-age" in change.headers["set-cookie"].lower()  # conserva «Recuérdame»

    assert refresh(other).status_code == 401
    assert refresh(client).status_code == 200


@pytest.mark.users
def test_admin_changing_a_password_revokes_that_users_sessions(client, db):
    _, doctor, _ = create_clinic_with_doctor(db, "Clinica Uno", EMAIL)
    admin_email = "admin@clinica-uno.com"
    from app.auth.security import hash_password
    from app.models import User

    db.add(User(name="Adm", email=admin_email, hashed_password=hash_password(PASSWORD), role="admin",
                is_active=True, clinic_id=doctor.clinic_id))
    db.commit()
    doctor_id = doctor.id

    target = TestClient(app)
    login(target)
    token = login(client, email=admin_email).json()["access_token"]
    assert client.patch(f"/users/{doctor_id}", json={"password": NEW_PASSWORD}, headers=bearer(token)).status_code == 200
    assert refresh(target).status_code == 401


@pytest.mark.users
def test_deactivating_a_user_revokes_sessions_and_reactivating_does_not_reopen_them(client, db):
    _, doctor, _ = create_clinic_with_doctor(db, "Clinica Uno", EMAIL)
    from app.auth.security import hash_password
    from app.models import User

    db.add(User(name="Adm", email="admin@clinica-uno.com", hashed_password=hash_password(PASSWORD), role="admin",
                is_active=True, clinic_id=doctor.clinic_id))
    db.commit()
    doctor_id = doctor.id
    target = TestClient(app)
    login(target)
    token = login(client, email="admin@clinica-uno.com").json()["access_token"]
    assert client.post(f"/users/{doctor_id}/deactivate", headers=bearer(token)).status_code == 200
    assert client.post(f"/users/{doctor_id}/activate", headers=bearer(token)).status_code == 200
    assert refresh(target).status_code == 401


def test_access_token_with_another_users_session_is_rejected(client, account, db):
    """Un `sid` activo solo vale para el usuario dueño de esa sesión."""
    from app.auth.jwt_handler import create_access_token

    login(client)
    family = db.query(AuthSession).one().family_id
    create_clinic_with_doctor(db, "Clinica Dos", "otro@clinica-dos.com")
    forged = create_access_token({"sub": "otro@clinica-dos.com", "role": "doctor", "sid": family})
    assert client.get("/auth/me", headers=bearer(forged)).status_code == 401


def run_rotation(token, results):
    session = SessionLocal()
    try:
        results.append(session_service.rotate(session, token) is not None)
    finally:
        session.close()


def test_revocation_reaches_a_rotation_in_progress(monkeypatch, client, account, db):
    """Dos conexiones reales: el token que crea la rotación tampoco sobrevive."""
    login(client)
    token = client.cookies[COOKIE]
    user_id = db.query(AuthSession).one().user_id
    added = threading.Event()
    original = session_service._add_token

    def slow_add(*args):
        created = original(*args)
        args[0].flush()
        added.set()
        time.sleep(0.6)
        return created

    monkeypatch.setattr(session_service, "_add_token", slow_add)
    results = []
    thread = threading.Thread(target=run_rotation, args=(token, results))
    thread.start()
    assert added.wait(10)

    revoker = SessionLocal()
    session_service.revoke_user_sessions(revoker, user_id)
    revoker.commit()
    revoker.close()
    thread.join(10)

    db.expire_all()
    rows = db.query(AuthSession).all()
    assert results == [True] and len(rows) == 2 and all(row.revoked_at is not None for row in rows)


def test_simultaneous_renewals_create_a_single_token(client, account, db):
    login(client)
    token = client.cookies[COOKIE]
    results = []
    threads = [threading.Thread(target=run_rotation, args=(token, results)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)

    assert results == [True] * 4
    db.expire_all()
    assert db.query(AuthSession).count() == 2
    assert db.query(AuthSession).filter(AuthSession.revoked_at.isnot(None)).count() == 0


def test_inactive_user_cannot_renew(client, account, db):
    from app.models import User

    login(client)
    db.query(User).filter(User.email == EMAIL).update({"is_active": False})
    db.commit()
    assert refresh(client).status_code == 401


def test_login_purges_long_expired_sessions(client, account, db):
    login(client)
    db.query(AuthSession).update({"expires_at": datetime.now(timezone.utc) - timedelta(days=2)})
    db.commit()
    login(client)
    db.expire_all()
    assert db.query(AuthSession).count() == 1


@pytest.mark.isolation
def test_sessions_stay_within_their_user_and_clinic(db):
    _, first, _ = create_clinic_with_doctor(db, "Clinica Uno", EMAIL)
    _, second, _ = create_clinic_with_doctor(db, "Clinica Dos", "sesion@clinica-dos.com")
    first_id, second_id, second_clinic = first.id, second.id, second.clinic_id
    issued = session_service.start(db, first, False)
    other = session_service.start(db, second, False)

    session_service.revoke_user_sessions(db, first_id)
    db.commit()

    assert not session_service.family_is_active(db, issued.family_id, first_id)
    assert session_service.family_is_active(db, other.family_id, second_id)
    row = db.query(AuthSession).filter(AuthSession.user_id == second_id).one()
    assert row.clinic_id == second_clinic


@pytest.mark.isolation
def test_database_rejects_a_session_with_another_clinic(db):
    from sqlalchemy.exc import IntegrityError

    _, first, _ = create_clinic_with_doctor(db, "Clinica Uno", EMAIL)
    _, second, _ = create_clinic_with_doctor(db, "Clinica Dos", "sesion@clinica-dos.com")
    db.add(AuthSession(
        user_id=first.id, clinic_id=second.clinic_id, family_id="f", token_hash="h" * 64, remember_me=False,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.rbac
@pytest.mark.parametrize("role", ["admin", "doctor", "receptionist"])
def test_every_role_can_renew_and_close_its_session(client, db, role):
    from app.auth.security import hash_password
    from app.models import User

    clinic, _, _ = create_clinic_with_doctor(db, "Clinica Uno", "otro@clinica-uno.com")
    email = f"{role}@clinica-uno.com"
    db.add(User(name=role, email=email, hashed_password=hash_password(PASSWORD), role=role,
                is_active=True, clinic_id=clinic.id))
    db.commit()
    login(client, email=email)
    assert refresh(client).status_code == 200
    assert client.post("/auth/logout", headers=ORIGIN).status_code == 200
