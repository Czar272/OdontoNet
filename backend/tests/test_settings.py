"""Configuración por ambientes, arranque en producción y alta inicial (ODON-234)."""
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core import startup
from app.core.settings import (
    Settings,
    ensure_safe_environment,
    environment_problems,
    get_database_url,
    get_settings,
)
from app.database.connection import SessionLocal, engine
from app.models import AuditEvent, Clinic, User
from app.services import email_service
from scripts import bootstrap_clinic
from scripts.bootstrap_clinic import BootstrapError, bootstrap
from tests.conftest import PASSWORD

pytestmark = pytest.mark.deployment

BACKEND_DIR = Path(__file__).resolve().parents[1]

PRODUCTION = {
    "APP_ENV": "production",
    "DATABASE_URL": "postgresql+psycopg2://odontonet:clave@db:5432/odontonet",
    "SECRET_KEY": "k" * 48,
    "CORS_ORIGINS": "",
    "ALLOWED_HOSTS": "odontonet.internal,localhost",
    "FRONTEND_URL": "https://odontonet.internal",
    "TRUST_PROXY_HEADERS": "true",
    "IMAGE_STORAGE_DIR": "/data/images",
}


def production(**changes) -> Settings:
    return Settings.model_validate({**PRODUCTION, **changes})


def test_valid_production_has_no_problems():
    assert environment_problems(production()) == []
    ensure_safe_environment(production())


@pytest.mark.parametrize(("variable", "value", "expected"), [
    ("SECRET_KEY", "REEMPLAZAR_CON_CLAVE_ALEATORIA_DE_AL_MENOS_32_BYTES", "SECRET_KEY"),
    ("SECRET_KEY", "test-only-secret-key-at-least-32-bytes-long", "SECRET_KEY"),
    ("DATABASE_URL", "postgresql://o:REEMPLAZAR@db/odontonet", "DATABASE_URL"),
    ("DATABASE_URL", "postgresql://o:clave@db/odontonet_test", "base de pruebas"),
    ("BCRYPT_ROUNDS", "4", "BCRYPT_ROUNDS"),
    ("CORS_ORIGINS", "http://localhost:5173", "CORS_ORIGINS"),
    ("ALLOWED_HOSTS", "localhost,127.0.0.1", "ALLOWED_HOSTS"),
    ("FRONTEND_URL", "http://odontonet.internal", "FRONTEND_URL"),
    ("FRONTEND_URL", "https://localhost", "FRONTEND_URL"),
    ("TRUST_PROXY_HEADERS", "false", "TRUST_PROXY_HEADERS"),
    ("IMAGE_STORAGE_DIR", "", "IMAGE_STORAGE_DIR"),
    ("IMAGE_STORAGE_DIR", "storage/images", "IMAGE_STORAGE_DIR"),
])
def test_production_rejects_insecure_value(variable, value, expected):
    problems = environment_problems(production(**{variable: value}))
    assert len(problems) == 1 and expected in problems[0]


def test_every_problem_is_reported_at_once():
    settings = production(TRUST_PROXY_HEADERS="false", FRONTEND_URL="http://x.internal")
    with pytest.raises(RuntimeError) as error:
        ensure_safe_environment(settings)
    assert "TRUST_PROXY_HEADERS" in str(error.value) and "FRONTEND_URL" in str(error.value)


def test_smtp_is_optional_in_production():
    assert production().smtp_host == ""
    assert environment_problems(production()) == []


def test_development_keeps_local_defaults():
    settings = Settings.model_validate({"DATABASE_URL": "postgresql://o:c@localhost/odontonet", "SECRET_KEY": "k" * 32})
    assert settings.app_env == "development" and environment_problems(settings) == []


def test_test_environment_requires_test_database():
    settings = Settings.model_validate({
        "APP_ENV": "test", "DATABASE_URL": "postgresql://o:c@localhost/odontonet", "SECRET_KEY": "k" * 32,
    })
    assert "_test" in environment_problems(settings)[0]


def test_tests_run_as_test_environment():
    assert get_settings().app_env == "test"


def test_invalid_value_names_the_variable_but_never_its_value(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "valor-corto-reservado")
    with pytest.raises(RuntimeError) as error:
        get_settings()
    assert "SECRET_KEY" in str(error.value) and "valor-corto-reservado" not in str(error.value)


def test_unknown_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(RuntimeError, match="APP_ENV"):
        get_settings()


def test_blank_number_uses_the_default(monkeypatch):
    monkeypatch.setenv("LOGIN_LOCK_MINUTES", "  ")
    assert get_settings().login_lock_minutes == 15


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("sí", True), ("si", True), ("false", False), ("0", False)])
def test_boolean_variables(monkeypatch, raw, expected):
    monkeypatch.setenv("SMTP_STARTTLS", raw)
    assert get_settings().smtp_starttls is expected


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("TRUE", True), ("1", False), ("yes", False), ("sí", False)])
def test_trusting_the_proxy_requires_an_explicit_true(monkeypatch, raw, expected):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", raw)
    assert get_settings().trust_proxy_headers is expected


def test_text_values_are_kept_literally(monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", " con espacios ")
    assert get_settings().smtp_password == " con espacios "


def test_zero_disables_password_recovery_requests(monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_MAX_PER_HOUR", "0")
    assert get_settings().password_reset_max_per_hour == 0


def test_database_tools_only_need_the_database_url(monkeypatch):
    monkeypatch.setenv("SMTP_STARTTLS", "valor-invalido")
    monkeypatch.delenv("SECRET_KEY")
    assert get_database_url() == os.environ["DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", " ")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_database_url()


# --- Arranque real del módulo, en un proceso aparte ------------------------------


def import_app(extra: dict[str, str]) -> subprocess.CompletedProcess:
    code = (
        "from app.main import app; "
        "print('docs' if app.docs_url or app.redoc_url or app.openapi_url else 'sin-docs')"
    )
    return subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, env={**os.environ, **PRODUCTION, "BCRYPT_ROUNDS": "12", "PYTHONUTF8": "1", **extra},
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def test_production_process_starts_without_interactive_docs():
    result = import_app({})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("sin-docs")


def test_development_process_keeps_interactive_docs():
    result = import_app({"APP_ENV": "development"})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("docs")


def test_production_process_refuses_insecure_configuration():
    result = import_app({"SECRET_KEY": "REEMPLAZAR_CON_CLAVE_ALEATORIA_DE_AL_MENOS_32_BYTES"})
    assert result.returncode != 0
    assert "Configuración insegura" in result.stderr


# --- Migraciones controladas -------------------------------------------------------


def test_schema_check_passes_when_up_to_date():
    startup.ensure_schema_current(engine)


def test_schema_check_stops_when_database_is_behind(monkeypatch):
    monkeypatch.setattr(startup, "expected_revision", lambda: "revision_futura")
    with pytest.raises(RuntimeError, match="revision_futura"):
        startup.ensure_schema_current(engine)


def test_production_startup_checks_the_schema(monkeypatch):
    def outdated(_engine):
        raise RuntimeError("base desactualizada")

    monkeypatch.setattr(main, "settings", production())
    monkeypatch.setattr(main, "ensure_schema_current", outdated)
    with pytest.raises(RuntimeError, match="base desactualizada"):
        with TestClient(main.app):
            pass


def test_other_environments_do_not_check_the_schema(monkeypatch):
    def unexpected(_engine):
        raise AssertionError("no debe comprobarse fuera de producción")

    monkeypatch.setattr(main, "ensure_schema_current", unexpected)
    with TestClient(main.app):
        pass


# --- Correo opcional ----------------------------------------------------------------


def test_production_without_smtp_never_logs_the_body(monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SMTP_HOST", "")
    with caplog.at_level(logging.INFO, logger="odontonet.email"):
        email_service.send_email("persona@ejemplo.com", "Asunto", "enlace-privado")
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "SMTP" in text and "enlace-privado" not in text and "persona@ejemplo.com" not in text


def test_development_without_smtp_logs_the_body(monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SMTP_HOST", "")
    with caplog.at_level(logging.INFO, logger="odontonet.email"):
        email_service.send_email("persona@ejemplo.com", "Asunto", "enlace-de-prueba")
    assert "enlace-de-prueba" in " ".join(record.getMessage() for record in caplog.records)


# --- Alta inicial -------------------------------------------------------------------


def create_first(db, **changes):
    values = {
        "clinic_name": "Clínica Inicial", "admin_name": "Administración",
        "admin_email": "admin@inicial.com", "password": PASSWORD,
    }
    return bootstrap(db, **{**values, **changes})


def test_bootstrap_creates_clinic_and_admin_who_can_log_in(db, client):
    admin = create_first(db)
    clinic = db.get(Clinic, admin.clinic_id)
    assert (clinic.name, clinic.timezone, admin.role, admin.is_active) == (
        "Clínica Inicial", "America/Guatemala", "admin", True)
    response = client.post("/auth/login", json={"email": "admin@inicial.com", "password": PASSWORD})
    assert response.status_code == 200, response.text


def test_bootstrap_is_audited_without_personal_data(db):
    admin = create_first(db)
    events = db.query(AuditEvent).order_by(AuditEvent.id).all()
    assert [(e.action, e.entity_type, e.entity_id, e.actor_user_id) for e in events] == [
        ("clinic.created", "clinic", admin.clinic_id, admin.id),
        ("user.created", "user", admin.id, admin.id),
    ]
    assert all(e.fields is None for e in events)


def test_bootstrap_refuses_an_installation_with_a_clinic(db):
    create_first(db)
    with pytest.raises(BootstrapError, match="ya tiene una clínica"):
        create_first(db, clinic_name="Otra", admin_email="otra@inicial.com")
    assert db.query(Clinic).count() == 1 and db.query(User).count() == 1


@pytest.mark.parametrize(("changes", "message"), [
    ({"password": "corta"}, "caracteres"),
    ({"password": "1234567890"}, "filtradas"),
    ({"timezone": "Marte/Base"}, "zona horaria"),
    ({"admin_email": "no-es-correo"}, "correo"),
    ({"clinic_name": "   "}, "obligatorios"),
])
def test_bootstrap_rejects_invalid_data(db, changes, message):
    with pytest.raises(BootstrapError, match=message):
        create_first(db, **changes)
    assert db.query(Clinic).count() == 0


ARGS = ["--clinic-name", "Clínica CLI", "--admin-name", "Adm", "--admin-email", "cli@inicial.com"]


def test_bootstrap_command(monkeypatch, capsys):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", PASSWORD)
    assert bootstrap_clinic.main(ARGS) == 0
    assert "cli@inicial.com" in capsys.readouterr().out
    with SessionLocal() as session:
        assert session.query(Clinic).one().name == "Clínica CLI"


def test_bootstrap_command_reports_errors_without_traceback(monkeypatch, capsys):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "corta")
    assert bootstrap_clinic.main(ARGS) == 2
    assert capsys.readouterr().out.startswith("Error:")


def test_bootstrap_command_asks_twice_when_no_variable(monkeypatch, capsys):
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    answers = iter([PASSWORD, "distinta"])
    monkeypatch.setattr(bootstrap_clinic.getpass, "getpass", lambda _prompt: next(answers))
    assert bootstrap_clinic.main(ARGS) == 2
    assert "no coinciden" in capsys.readouterr().out
