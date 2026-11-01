"""Configuración de pruebas.

Las pruebas usan una base PostgreSQL dedicada cuyo nombre debe terminar en
"_test". Las tablas se vacían antes de cada prueba, por lo que nunca deben
apuntar a la base de desarrollo.

Por defecto la URL se deriva de DATABASE_URL en backend/.env cambiando el
nombre de la base a "<nombre>_test". TEST_DATABASE_URL permite sobrescribirla.
"""
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _resolve_test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit

    dev_url = dotenv_values(BACKEND_DIR / ".env").get("DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dev_url:
        pytest.exit("No se encontró DATABASE_URL en backend/.env ni TEST_DATABASE_URL.", returncode=2)

    url = make_url(dev_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


TEST_DATABASE_URL = _resolve_test_database_url()
_test_url = make_url(TEST_DATABASE_URL)

if not (_test_url.database or "").endswith("_test"):
    pytest.exit("La base de pruebas debe tener un nombre terminado en _test.", returncode=2)

# Verificación previa con el error completo (pytest solo mostraría la primera línea).
try:
    with create_engine(TEST_DATABASE_URL).connect() as _conn:
        _conn.execute(text("SELECT 1"))
except Exception as exc:  # noqa: BLE001
    pytest.exit(
        f"No se pudo conectar a la base de pruebas {_test_url.render_as_string(hide_password=True)}\n"
        f"{exc}\n"
        f"¿Existe la base? Créala con: docker exec odontonet-db createdb -U {_test_url.username} {_test_url.database}\n"
        "Si definiste TEST_DATABASE_URL a mano, elimínala con: Remove-Item Env:TEST_DATABASE_URL",
        returncode=2,
    )

# Debe definirse antes de importar la app: load_dotenv no sobrescribe variables existentes.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database.connection import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Clinic, Doctor, User  # noqa: E402

PASSWORD = "Test-Password-123"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Aplica las migraciones Alembic (no create_all) sobre la base de pruebas."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE patients, doctors, users, clinics RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def create_clinic_with_doctor(db, clinic_name: str, email: str, role: str = "doctor", active: bool = True):
    clinic = Clinic(name=clinic_name)
    db.add(clinic)
    db.flush()
    user = User(
        name=f"Dr. {clinic_name}",
        email=email,
        hashed_password=hash_password(PASSWORD),
        role=role,
        is_active=active,
        clinic_id=clinic.id,
    )
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, clinic_id=clinic.id)
    db.add(doctor)
    db.commit()
    return clinic, user, doctor


def auth_headers(client, email: str) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def two_clinics(db, client):
    """Dos clínicas independientes, cada una con un usuario doctor y su token."""
    clinic_a, user_a, doctor_a = create_clinic_with_doctor(db, "Clinica A", "doc.a@test.com")
    clinic_b, user_b, doctor_b = create_clinic_with_doctor(db, "Clinica B", "doc.b@test.com")
    return {
        "a": {"clinic": clinic_a.id, "user": user_a.id, "doctor": doctor_a.id, "headers": auth_headers(client, "doc.a@test.com")},
        "b": {"clinic": clinic_b.id, "user": user_b.id, "doctor": doctor_b.id, "headers": auth_headers(client, "doc.b@test.com")},
    }
