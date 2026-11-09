"""Configuración tipada por ambiente (ODON-234).

Toda la configuración sale del entorno o de backend/.env; los secretos nunca se
escriben en el código. `get_settings()` lee el entorno en cada llamada, sin
caché, para que un cambio de variable se vea de inmediato (las pruebas lo usan).

`APP_ENV` distingue tres ambientes: development (por defecto), test y
production. En producción la aplicación se niega a arrancar con valores de
ejemplo o inseguros: ver `environment_problems`.
"""
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

# HS256 necesita una clave de al menos 32 bytes (RFC 7518, sección 3.2).
MIN_SECRET_KEY_BYTES = 32
# bcrypt más barato solo tiene sentido en pruebas.
MIN_PRODUCTION_BCRYPT_ROUNDS = 12
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# Texto de las plantillas y de las claves de pruebas, CI y E2E.
_INSECURE_MARKERS = ("reemplazar", "test-only", "ci-only", "e2e-only", "not-for-production")


class Settings(BaseModel):
    """Una variable de entorno por campo, con el nombre del campo en mayúsculas."""

    model_config = ConfigDict(frozen=True, extra="ignore", alias_generator=str.upper, populate_by_name=True)

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = Field(min_length=1)

    # Sesión
    secret_key: str = Field(min_length=1)
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    # Duración máxima de la sesión (ODON-265); renovar no la alarga.
    session_expire_hours: int = Field(default=12, gt=0)
    remember_me_expire_days: int = Field(default=7, gt=0)
    # El navegador ve la API bajo /api, en desarrollo y en producción.
    session_cookie_path: str = "/api/auth"
    bcrypt_rounds: int = Field(default=12, ge=4, le=31)

    # Red
    cors_origins: str = "http://localhost:5173"
    allowed_hosts: str = "localhost,127.0.0.1"
    frontend_url: str = "http://localhost:5173"
    trust_proxy_headers: bool = False

    # Recuperación de contraseña y límite de intentos
    password_reset_expire_minutes: int = Field(default=30, gt=0)
    # 0 desactiva las solicitudes de recuperación.
    password_reset_max_per_hour: int = Field(default=3, ge=0)
    login_max_failures_per_account: int = Field(default=7, gt=0)
    login_max_failures_per_ip: int = Field(default=30, gt=0)
    login_window_minutes: int = Field(default=15, gt=0)
    login_lock_minutes: int = Field(default=15, gt=0)
    password_reset_max_per_ip: int = Field(default=10, gt=0)
    password_reset_confirm_max_failures_per_ip: int = Field(default=30, gt=0)

    # Correo: opcional también en producción (la clínica puede no tener internet).
    smtp_host: str = ""
    smtp_port: int = Field(default=587, gt=0)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "OdontoNet <no-reply@odontonet.local>"
    smtp_starttls: bool = True

    # Imágenes clínicas
    image_storage_dir: str = ""
    image_max_mb: float = Field(default=10, gt=0)

    @field_validator("trust_proxy_headers", mode="before")
    @classmethod
    def _trust_proxy_only_when_explicit(cls, value):
        """Solo "true": confiar por error en X-Forwarded-For deja evadir el límite por IP."""
        return value.strip().lower() == "true" if isinstance(value, str) else value

    @field_validator("smtp_starttls", mode="before")
    @classmethod
    def _accept_spanish_yes(cls, value):
        if isinstance(value, str) and value.strip().lower() in ("si", "sí"):
            return True
        return value

    @field_validator("secret_key")
    @classmethod
    def _secret_key_long_enough(cls, value: str) -> str:
        if len(value.encode("utf-8")) < MIN_SECRET_KEY_BYTES:
            raise ValueError(
                f"debe tener al menos {MIN_SECRET_KEY_BYTES} bytes. Genera una con: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _from_environment() -> dict[str, str]:
    """Variables definidas. Vacía en un campo no textual equivale a no definida."""
    values: dict[str, str] = {}
    for name, field in Settings.model_fields.items():
        variable = name.upper()
        raw = os.environ.get(variable)
        if raw is None or (raw.strip() == "" and field.annotation is not str):
            continue
        # El texto se conserva literal: una contraseña puede tener espacios.
        values[variable] = raw if field.annotation is str else raw.strip()
    return values


def get_database_url() -> str:
    """Solo la conexión: migraciones y respaldos no deben depender del resto de
    la configuración, ni fallar por una errata ajena a la base."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL no está configurada. Revisa backend/.env")
    return url


def get_settings() -> Settings:
    """Lee y valida la configuración. El mensaje de error nombra la variable,
    nunca su valor: va al log y puede tratarse de un secreto."""
    try:
        return Settings.model_validate(_from_environment())
    except ValidationError as exc:
        details = [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False, include_context=False)
        ]
        raise RuntimeError("Configuración inválida. Revisa backend/.env: " + "; ".join(details)) from None


def _split(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _has_insecure_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _INSECURE_MARKERS)


def _is_absolute_path(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _production_problems(settings: Settings) -> list[str]:
    problems: list[str] = []

    if _has_insecure_marker(settings.secret_key):
        problems.append("SECRET_KEY conserva un valor de ejemplo o de pruebas.")
    if _has_insecure_marker(settings.database_url):
        problems.append("DATABASE_URL conserva un valor de ejemplo o de pruebas.")
    if (make_url(settings.database_url).database or "").endswith("_test"):
        problems.append("DATABASE_URL apunta a una base de pruebas (*_test).")
    if settings.bcrypt_rounds < MIN_PRODUCTION_BCRYPT_ROUNDS:
        problems.append(f"BCRYPT_ROUNDS debe ser al menos {MIN_PRODUCTION_BCRYPT_ROUNDS}.")

    if any(urlsplit(origin).scheme != "https" for origin in _split(settings.cors_origins)):
        problems.append("CORS_ORIGINS solo admite orígenes https (déjala vacía si todo se sirve desde un origen).")
    if not set(_split(settings.allowed_hosts)) - _LOCAL_HOSTS:
        problems.append("ALLOWED_HOSTS debe incluir el nombre real del servidor.")

    frontend = urlsplit(settings.frontend_url)
    if frontend.scheme != "https" or frontend.hostname in _LOCAL_HOSTS:
        problems.append("FRONTEND_URL debe ser la dirección https real del sistema.")

    # Detrás de un solo proxy todos los clientes tendrían la misma IP y unos pocos
    # fallos bloquearían a toda la clínica.
    if not settings.trust_proxy_headers:
        problems.append("TRUST_PROXY_HEADERS debe ser true: en producción la API corre detrás del proxy.")

    if not settings.image_storage_dir or not _is_absolute_path(settings.image_storage_dir):
        problems.append("IMAGE_STORAGE_DIR debe ser una ruta absoluta (las imágenes clínicas se respaldan desde ahí).")

    return problems


def environment_problems(settings: Settings) -> list[str]:
    """Incompatibilidades entre el ambiente declarado y la configuración."""
    if settings.is_production:
        return _production_problems(settings)
    if settings.app_env == "test" and not (make_url(settings.database_url).database or "").endswith("_test"):
        return ["Con APP_ENV=test, DATABASE_URL debe apuntar a una base *_test."]
    return []


def ensure_safe_environment(settings: Settings) -> None:
    """Detiene el arranque y reporta todos los problemas de una vez."""
    problems = environment_problems(settings)
    if problems:
        raise RuntimeError(f"Configuración insegura para APP_ENV={settings.app_env}:\n- " + "\n- ".join(problems))
