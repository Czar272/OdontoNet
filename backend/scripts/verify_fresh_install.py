"""Comprueba que una instalación recién creada no arrastra datos de la prueba de aceptación (ODON-276).

Se corre justo después de `bootstrap_clinic`, antes de crear personal o registrar pacientes
(`docs/DEPLOYMENT.md`, «Pasar de la instalación de prueba a la definitiva»). Una instalación
limpia tiene:

- exactamente una clínica y un usuario (la administración creada por `bootstrap_clinic`);
- en la auditoría, solo los eventos de esa alta;
- cero filas en todas las demás tablas de datos (pacientes, agenda, expediente, imágenes,
  periodontograma, doctores…), salvo las de sesión e intentos de acceso, que se llenan al
  iniciar sesión para comprobar el sistema;
- la carpeta de imágenes sin archivos.

Solo lee: no corrige ni borra nada. Termina con código 1 si encuentra datos de más. Imprime
nombres de tablas y conteos, nunca datos de pacientes ni del personal.

Uso, desde backend/ con odonto_venv activo (o dentro del contenedor de la API):

    python -m scripts.verify_fresh_install
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

# Tablas que una instalación recién creada puede tener con filas.
EXPECTED_ROWS = {"clinics": 1, "users": 1}
BOOTSTRAP_AUDIT_ACTIONS = {"clinic.created", "user.created"}
# Se llenan solo con iniciar sesión o intentar hacerlo; no contienen datos clínicos.
SESSION_TABLES = {"auth_sessions", "auth_attempts", "password_reset_tokens"}
IGNORED_TABLES = {"alembic_version"}


@dataclass
class FreshInstallReport:
    counts: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    image_files: int = 0

    @property
    def clean(self) -> bool:
        return not self.problems


def check(db: Session, image_dir: Path | None) -> FreshInstallReport:
    import app.models  # noqa: F401  registra todas las tablas en los metadatos
    from app.database.connection import Base
    from app.models import AuditEvent

    report = FreshInstallReport()
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        if table.name in IGNORED_TABLES:
            continue
        n = db.execute(select(func.count()).select_from(table)).scalar_one()
        report.counts[table.name] = n
        if table.name in EXPECTED_ROWS:
            if n != EXPECTED_ROWS[table.name]:
                report.problems.append(f"{table.name}: {n} filas (se esperaba {EXPECTED_ROWS[table.name]})")
        elif table.name == "audit_events":
            extra = db.execute(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.action.not_in(BOOTSTRAP_AUDIT_ACTIONS))
            ).scalar_one()
            if extra:
                report.problems.append(f"audit_events: {extra} eventos que no son del alta inicial")
        elif table.name not in SESSION_TABLES and n:
            report.problems.append(f"{table.name}: {n} filas (se esperaba 0)")
    if image_dir is not None:
        if not image_dir.exists():
            report.problems.append(f"La carpeta de imágenes no existe: {image_dir}")
        else:
            report.image_files = sum(1 for p in image_dir.rglob("*") if p.is_file())
            if report.image_files:
                report.problems.append(f"La carpeta de imágenes tiene {report.image_files} archivos (se esperaba ninguno)")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    from app.core.settings import get_settings
    from app.database.connection import SessionLocal

    argparse.ArgumentParser(description="Comprueba que una instalación nueva no arrastra datos de prueba.").parse_args(argv)
    settings = get_settings()
    image_dir = Path(settings.image_storage_dir) if settings.image_storage_dir else None
    with SessionLocal() as db:
        report = check(db, image_dir)
    print("Filas por tabla:")
    for name, n in report.counts.items():
        print(f"  {name}: {n}")
    print(f"Archivos en la carpeta de imágenes: {report.image_files}" if image_dir else "Sin IMAGE_STORAGE_DIR configurado.")
    if report.clean:
        print("Instalación limpia: solo la clínica y la administración del alta inicial.")
        return 0
    print("Se encontraron datos que no corresponden a una instalación nueva:")
    for problem in report.problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
