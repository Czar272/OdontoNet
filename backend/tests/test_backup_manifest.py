"""Manifiesto de respaldos (ODON-226): lo restaurado debe coincidir con lo respaldado."""
import json

import pytest

from app.models import AuditEvent, Patient, User
from app.services import audit_service
from scripts import backup_manifest
from tests.conftest import create_clinic_with_doctor

pytestmark = [pytest.mark.backup]


@pytest.fixture
def data(db):
    clinic, user, _ = create_clinic_with_doctor(db, "Clinica Respaldo", "doc@respaldo-clinica.com")
    db.add(Patient(first_name="Paciente", last_name="Respaldo", clinic_id=clinic.id))
    db.commit()
    audit_service.record(db, db.get(User, user.id), "clinic.updated", "clinic", clinic.id, fields=["name"])
    db.commit()
    return {"db": db, "clinic": clinic.id, "user": user.id}


def test_manifest_has_counts_alembic_version_and_audit_tail(data):
    manifest = backup_manifest.build()
    assert manifest["format"] == backup_manifest.FORMAT_VERSION
    assert manifest["alembic_version"]
    assert manifest["row_counts"]["patients"] == 1
    assert manifest["row_counts"]["audit_events"] == 1
    tail = manifest["audit_chain_tails"][str(data["clinic"])]
    assert tail["last_id"] == data["db"].query(AuditEvent).one().id
    # Solo conteos e ids: ningún dato de pacientes.
    assert "Respaldo" not in json.dumps(manifest)


def test_identical_database_matches(data):
    manifest = backup_manifest.build()
    assert backup_manifest.compare(manifest, backup_manifest.build()) == []


def test_missing_rows_and_truncated_audit_are_detected(data):
    manifest = backup_manifest.build()
    restored = json.loads(json.dumps(manifest))
    restored["row_counts"]["patients"] = 0
    # Un respaldo al que le falta el final de la cadena de auditoría (ODON-222).
    restored["audit_chain_tails"] = {}
    restored["alembic_version"] = "otra"
    problems = backup_manifest.compare(manifest, restored)
    assert any("patients" in problem for problem in problems)
    assert any("auditoría" in problem for problem in problems)
    assert any("Alembic" in problem for problem in problems)


def test_missing_image_files_are_detected(data):
    manifest = backup_manifest.build()
    manifest["image_files"] = manifest["image_files"] + 3
    problems = backup_manifest.compare(manifest, backup_manifest.build())
    assert any("imágenes" in problem for problem in problems)


def test_cli_create_and_compare(data, scratch_dir, capsys):
    path = scratch_dir / "manifest.json"
    assert backup_manifest.main(["x", "create", str(path)]) == 0
    assert backup_manifest.main(["x", "compare", str(path)]) == 0
    data["db"].add(Patient(first_name="Otro", last_name="Paciente", clinic_id=data["clinic"]))
    data["db"].commit()
    assert backup_manifest.main(["x", "compare", str(path)]) == 1
    assert "patients" in capsys.readouterr().out
    assert backup_manifest.main(["x", "otra-cosa"]) == 2
