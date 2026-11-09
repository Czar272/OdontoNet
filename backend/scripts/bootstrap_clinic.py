"""Crea la primera clínica y su administración en una instalación nueva (ODON-234).

Cada instalación atiende una clínica. Solo funciona con la base sin clínicas:
no sirve para agregar otra ni para cambiar datos de una existente. Queda
registrado en la auditoría.

La contraseña se toma de BOOTSTRAP_ADMIN_PASSWORD o se pide por consola; nunca
va en la línea de comandos, para que no quede en el historial.

Uso, desde backend/:

    python -m scripts.bootstrap_clinic --clinic-name "Clínica X" \
        --admin-name "Nombre" --admin-email correo@ejemplo.com
"""
import argparse
import getpass
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pydantic import EmailStr, TypeAdapter, ValidationError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.core.password_policy import MAX_LENGTH, MIN_LENGTH, check_new_password  # noqa: E402
from app.core.settings import ensure_safe_environment, get_settings  # noqa: E402
from app.database.connection import SessionLocal  # noqa: E402
from app.models import Clinic, User  # noqa: E402
from app.services import audit_service  # noqa: E402

DEFAULT_TIMEZONE = "America/Guatemala"


class BootstrapError(Exception):
    """Dato inválido o instalación que ya tiene una clínica."""


def _valid_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (KeyError, ValueError, OSError):
        raise BootstrapError(f"La zona horaria {name!r} no existe (formato IANA, p. ej. {DEFAULT_TIMEZONE}).") from None
    return name


def _valid_email(email: str) -> str:
    try:
        return TypeAdapter(EmailStr).validate_python(email.strip())
    except ValidationError:
        raise BootstrapError("El correo de administración no es válido.") from None


def _valid_password(password: str) -> str:
    if not MIN_LENGTH <= len(password) <= MAX_LENGTH:
        raise BootstrapError(f"La contraseña debe tener entre {MIN_LENGTH} y {MAX_LENGTH} caracteres.")
    try:
        return check_new_password(password)
    except ValueError as exc:
        raise BootstrapError(str(exc)) from None


def bootstrap(db: Session, clinic_name: str, admin_name: str, admin_email: str, password: str,
              timezone: str = DEFAULT_TIMEZONE, address: str | None = None, phone: str | None = None) -> User:
    """Crea clínica, usuario `admin` y sus eventos de auditoría, en una transacción."""
    clinic_name, admin_name = clinic_name.strip(), admin_name.strip()
    if not clinic_name or not admin_name:
        raise BootstrapError("El nombre de la clínica y el de administración son obligatorios.")
    timezone = _valid_timezone(timezone)
    admin_email = _valid_email(admin_email)
    password = _valid_password(password)

    if db.query(Clinic.id).first() is not None:
        raise BootstrapError("Esta instalación ya tiene una clínica; no se cambió nada.")

    clinic = Clinic(name=clinic_name, address=address, phone=phone, timezone=timezone)
    db.add(clinic)
    db.flush()
    admin = User(name=admin_name, email=admin_email, hashed_password=hash_password(password),
                 role="admin", is_active=True, clinic_id=clinic.id)
    db.add(admin)
    db.flush()
    audit_service.record(db, admin, "clinic.created", "clinic", clinic.id)
    audit_service.record(db, admin, "user.created", "user", admin.id)
    db.commit()
    return admin


def _read_password() -> str:
    from_environment = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if from_environment:
        return from_environment
    password = getpass.getpass("Contraseña de administración: ")
    if password != getpass.getpass("Repite la contraseña: "):
        raise BootstrapError("Las contraseñas no coinciden.")
    return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crea la primera clínica y su administración.")
    parser.add_argument("--clinic-name", required=True)
    parser.add_argument("--admin-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--address")
    parser.add_argument("--phone")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        ensure_safe_environment(get_settings())
        admin = bootstrap(db, args.clinic_name, args.admin_name, args.admin_email, _read_password(),
                          timezone=args.timezone, address=args.address, phone=args.phone)
        email = admin.email
    except (BootstrapError, RuntimeError) as exc:
        db.rollback()
        print(f"Error: {exc}")
        return 2
    finally:
        db.close()
    print(f"Listo. Inicia sesión con {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
