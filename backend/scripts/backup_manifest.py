"""Manifiesto de un respaldo (ODON-226).

Al respaldar se guarda un resumen de la base junto con el volcado; al ensayar
la restauración se compara la base restaurada contra ese resumen. Así se sabe
que lo restaurado es exactamente lo respaldado, incluida la cola de la cadena
de auditoría (el borrado de los eventos más recientes no lo detecta la cadena
sola, ODON-222).

Solo contiene conteos, la versión de Alembic y los ids y hashes de auditoría:
ningún dato de pacientes.

El manifiesto y el volcado salen del mismo estado de la base: `dump` abre una
transacción REPEATABLE READ, exporta su snapshot (pg_export_snapshot) y corre
pg_dump --snapshot con él mientras calcula el manifiesto. Así, lo que pase en la
API durante el respaldo no produce falsos positivos en el ensayo.

Uso, desde backend/ (DATABASE_URL e IMAGE_STORAGE_DIR del entorno o de .env):

    python -m scripts.backup_manifest dump <carpeta> <contenedor> <usuario> <base>
    python -m scripts.backup_manifest create <archivo.json>
    python -m scripts.backup_manifest compare <archivo.json>   # sale con 1 si difiere
    python -m scripts.backup_manifest restore-url <base>        # DATABASE_URL apuntando a otra base
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.database.connection import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401  (registra las tablas)
from app.services.image_storage import DEFAULT_STORAGE_DIR  # noqa: E402

FORMAT_VERSION = 1


def _image_files() -> int:
    root = Path(os.getenv("IMAGE_STORAGE_DIR") or DEFAULT_STORAGE_DIR)
    return sum(1 for path in root.rglob("*") if path.is_file()) if root.exists() else 0


def build(conn=None) -> dict:
    """Resumen de la base (y del número de archivos de imágenes). Con `conn`,
    se calcula dentro de esa transacción (mismo snapshot que el volcado)."""
    if conn is None:
        with engine.connect() as own:
            return build(own)
    alembic = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    counts = {
        table.name: conn.execute(text(f'SELECT count(*) FROM "{table.name}"')).scalar()
        for table in Base.metadata.sorted_tables
    }
    audit = {
        str(clinic): {"last_id": last_id, "last_hash": last_hash}
        for clinic, last_id, last_hash in conn.execute(text(
            "SELECT DISTINCT ON (clinic_id) clinic_id, id, hash FROM audit_events "
            "ORDER BY clinic_id, id DESC"
        ))
    }
    return {
        "format": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "alembic_version": alembic,
        "row_counts": counts,
        "audit_chain_tails": audit,
        "image_files": _image_files(),
    }


def compare(expected: dict, actual: dict) -> list[str]:
    """Diferencias entre el manifiesto respaldado y la base restaurada."""
    problems = []
    if expected.get("format") != FORMAT_VERSION:
        problems.append(f"formato de manifiesto desconocido: {expected.get('format')}")
    if expected["alembic_version"] != actual["alembic_version"]:
        problems.append(f"versión de Alembic: respaldo {expected['alembic_version']}, restaurada {actual['alembic_version']}")
    for table, count in expected["row_counts"].items():
        restored = actual["row_counts"].get(table)
        if restored != count:
            problems.append(f"tabla {table}: respaldo {count} filas, restaurada {restored}")
    for clinic, tail in expected["audit_chain_tails"].items():
        if actual["audit_chain_tails"].get(clinic) != tail:
            problems.append(f"auditoría de la clínica {clinic}: el último evento no coincide con el respaldo")
    if actual["image_files"] < expected["image_files"]:
        problems.append(f"imágenes: respaldo {expected['image_files']} archivos, restaurados {actual['image_files']}")
    return problems


def dump(out_dir: Path, container: str, user: str, database: str) -> None:
    """Volcado y manifiesto del mismo snapshot. El volcado queda en out_dir y se
    borra del contenedor aunque algo falle."""
    out_dir.mkdir(parents=True, exist_ok=True)
    remote = "/tmp/odontonet.dump"
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="REPEATABLE READ")
        with conn.begin():
            snapshot = conn.execute(text("SELECT pg_export_snapshot()")).scalar()
            try:
                subprocess.run(
                    ["docker", "exec", container, "pg_dump", "-U", user, "-d", database, "-Fc",
                     f"--snapshot={snapshot}", "-f", remote],
                    check=True,
                )
                local = out_dir / "odontonet.dump"
                subprocess.run(["docker", "cp", f"{container}:{remote}", str(local)], check=True,
                               stdout=subprocess.DEVNULL)
            finally:
                subprocess.run(["docker", "exec", container, "rm", "-f", remote], check=False)
            if not local.exists() or local.stat().st_size == 0:
                raise RuntimeError("El volcado de la base está vacío o no se copió.")
            manifest = build(conn)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def restore_url(database: str) -> str:
    """DATABASE_URL apuntando a otra base del mismo servidor (ensayo de restauración)."""
    url = make_url(os.environ.get("DATABASE_URL") or str(engine.url)).set(database=database)
    if url.database != database:
        raise RuntimeError("No se pudo apuntar la URL a la base temporal.")
    return url.render_as_string(hide_password=False)


def main(argv: list[str]) -> int:
    if len(argv) == 6 and argv[1] == "dump":
        dump(Path(argv[2]), argv[3], argv[4], argv[5])
        print(f"Volcado y manifiesto (mismo snapshot) en {argv[2]}")
        return 0
    if len(argv) == 3 and argv[1] == "restore-url":
        print(restore_url(argv[2]))
        return 0
    if len(argv) != 3 or argv[1] not in ("create", "compare"):
        print(__doc__)
        return 2
    path = Path(argv[2])
    if argv[1] == "create":
        path.write_text(json.dumps(build(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Manifiesto escrito en {path}")
        return 0
    problems = compare(json.loads(path.read_text(encoding="utf-8")), build())
    if problems:
        print("La restauración NO coincide con el respaldo:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("La restauración coincide con el manifiesto del respaldo.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
