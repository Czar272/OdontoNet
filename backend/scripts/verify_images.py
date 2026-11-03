"""Verificación de imágenes clínicas contra el almacenamiento (ODON-166).

Se corre después de restaurar un respaldo, o periódicamente, para comprobar
que la base y la carpeta de imágenes están completas y coinciden:

- faltantes: registros sin archivo;
- alteradas: archivos cuyo SHA-256 no coincide con el registrado;
- huérfanos: archivos sin registro (p. ej. un respaldo de la carpeta más
  nuevo que el de la base);
- ajenos: archivos con un nombre que el almacenamiento nunca genera
  (temporales de una escritura interrumpida, copias manuales).

Solo lee: no corrige, mueve ni borra nada. Termina con código 1 si encuentra
problemas. Imprime claves e ids, nunca datos de pacientes.

Uso, desde backend/ con odonto_venv activo:

    python -m scripts.verify_images
"""

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session  # noqa: E402

from app.models import PatientImage  # noqa: E402
from app.services.image_storage import (  # noqa: E402
    LocalImageStorage,
    StoredImageNotFound,
    get_image_storage,
)


@dataclass
class Report:
    checked: int = 0
    missing: list[str] = field(default_factory=list)
    altered: list[str] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    foreign: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.altered or self.orphans or self.foreign)


def verify(db: Session, storage: LocalImageStorage) -> Report:
    report = Report()
    registered = set()

    for image_id, key, sha256 in db.query(
        PatientImage.id, PatientImage.storage_key, PatientImage.sha256
    ).order_by(PatientImage.id).yield_per(200):
        report.checked += 1
        registered.add(key)
        try:
            data = storage.read(key)
        except StoredImageNotFound:
            report.missing.append(f"imagen {image_id}: {key}")
            continue
        if hashlib.sha256(data).hexdigest() != sha256:
            report.altered.append(f"imagen {image_id}: {key}")

    stored = set(storage.keys())
    report.orphans = sorted(stored - registered)

    if storage.root.exists():
        report.foreign = sorted(
            path.relative_to(storage.root).as_posix()
            for path in storage.root.rglob("*")
            if path.is_file() and path.relative_to(storage.root).as_posix() not in stored
        )
    return report


def main() -> int:
    from app.database.connection import SessionLocal

    storage = get_image_storage()
    if not isinstance(storage, LocalImageStorage):
        print("Solo se verifica el almacenamiento local.")
        return 2

    with SessionLocal() as db:
        report = verify(db, storage)

    print(f"Almacenamiento: {storage.root}")
    print(f"Imágenes registradas verificadas: {report.checked}")
    sections = [
        ("Registros sin archivo", report.missing),
        ("Archivos alterados (SHA-256 distinto)", report.altered),
        ("Archivos sin registro", report.orphans),
        ("Archivos ajenos al almacenamiento", report.foreign),
    ]
    for title, items in sections:
        print(f"{title}: {len(items)}")
        for item in items:
            print(f"  - {item}")

    print("OK: base e imágenes coinciden." if report.ok else "Se encontraron diferencias.")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
