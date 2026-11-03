"""Configuración de pruebas.

Las pruebas usan una base PostgreSQL dedicada cuyo nombre debe terminar en
"_test". Las tablas se vacían antes de cada prueba, por lo que nunca deben
apuntar a la base de desarrollo.

Por defecto la URL se deriva de DATABASE_URL en backend/.env cambiando el
nombre de la base a "<nombre>_test". TEST_DATABASE_URL permite sobrescribirla.
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Antes de importar la app: bcrypt barato solo en pruebas (ver app/auth/security.py).
os.environ.setdefault("BCRYPT_ROUNDS", "4")

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
# Las pruebas nunca escriben en la carpeta real de imágenes (ODON-166).
os.environ["IMAGE_STORAGE_DIR"] = tempfile.mkdtemp(prefix="odontonet-test-images-")
atexit.register(shutil.rmtree, os.environ["IMAGE_STORAGE_DIR"], ignore_errors=True)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event, text  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database.connection import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Clinic, Doctor, User  # noqa: E402
from app.services.image_storage import LocalImageStorage, get_image_storage  # noqa: E402

PASSWORD = "Test-Password-123"

TEST_CATEGORIES = {"auth", "patients", "doctors", "users", "api", "seed", "isolation", "rbac", "appointments", "records", "images"}


def pytest_collection_modifyitems(config, items):
    """Exige que cada prueba declare al menos una categoría (marcador)."""
    uncategorized = [
        item.nodeid
        for item in items
        if not TEST_CATEGORIES & {marker.name for marker in item.iter_markers()}
    ]
    if uncategorized:
        raise pytest.UsageError(
            "Pruebas sin categoría (agrega un marcador de pytest.ini):\n  " + "\n  ".join(uncategorized)
        )


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Aplica las migraciones Alembic (no create_all) sobre la base de pruebas."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    yield


@event.listens_for(engine, "connect")
def _fast_test_commits(dbapi_connection, _record):
    """La base de pruebas no necesita durabilidad: sin esperar al disco en cada
    commit (synchronous_commit=off), sobre todo en Docker Desktop. Solo afecta
    a las conexiones de pytest; la base sigue siendo consistente."""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET synchronous_commit TO off")
    cursor.close()


@pytest.fixture(scope="session")
def cleanup_sql(migrated_database) -> str:
    """SQL que vacía todas las tablas del modelo y reinicia sus ids.

    DELETE en orden inverso de dependencias en vez de TRUNCATE: con tablas
    casi vacías es unas 15 veces más rápido, porque TRUNCATE recrea los
    archivos de cada tabla (en Docker Desktop, todavía más lento). La lista
    sale de los modelos, así que una tabla nueva se incluye sola."""
    tables = [table.name for table in reversed(Base.metadata.sorted_tables)]
    with engine.connect() as conn:
        sequences = [
            conn.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table}).scalar()
            for table in tables
        ]
    statements = [f"DELETE FROM {table}" for table in tables]
    statements += [f"ALTER SEQUENCE {sequence} RESTART" for sequence in sequences if sequence]
    return "; ".join(statements)


@pytest.fixture(autouse=True)
def clean_tables(cleanup_sql):
    with engine.begin() as conn:
        conn.exec_driver_sql(cleanup_sql)
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


@pytest.fixture
def scratch_dir():
    """Carpeta temporal propia de la prueba.

    No se usa tmp_path: en Windows el directorio base de pytest
    (%TEMP%/pytest-of-<usuario>) puede dar PermissionError."""
    path = Path(tempfile.mkdtemp(prefix="odontonet-test-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def image_storage(scratch_dir):
    """Almacenamiento de imágenes aislado por prueba."""
    storage = LocalImageStorage(scratch_dir / "images")
    app.dependency_overrides[get_image_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_image_storage, None)


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
