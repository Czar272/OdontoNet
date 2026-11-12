"""Comprobación de instalación limpia tras pasar de la UAT a la definitiva (ODON-276)."""
import pytest

from app.models import Patient
from app.services import audit_service
from scripts import verify_fresh_install
from scripts.bootstrap_clinic import bootstrap
from scripts.verify_fresh_install import check
from tests.conftest import PASSWORD, create_clinic_with_doctor

pytestmark = pytest.mark.deployment


def bootstrap_first(db):
    return bootstrap(db, clinic_name="Clínica Definitiva", admin_name="Administración",
                     admin_email="admin@definitiva.com", password=PASSWORD)


def test_fresh_install_after_bootstrap_is_clean(db, scratch_dir):
    bootstrap_first(db)
    report = check(db, scratch_dir)
    assert report.clean, report.problems
    assert report.counts["clinics"] == 1 and report.counts["users"] == 1
    assert report.counts["patients"] == 0 and report.image_files == 0


def test_logging_in_does_not_make_it_dirty(db, client, scratch_dir):
    bootstrap_first(db)
    response = client.post("/auth/login", json={"email": "admin@definitiva.com", "password": PASSWORD})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert check(db, scratch_dir).clean


def test_empty_database_is_not_a_finished_install(db, scratch_dir):
    report = check(db, scratch_dir)
    assert not report.clean
    assert "clinics: 0 filas (se esperaba 1)" in report.problems


def test_leftover_test_data_is_reported_by_table(db, scratch_dir):
    clinic, _, _ = create_clinic_with_doctor(db, "Clínica Prueba UAT", "doc@uat.com")
    db.add(Patient(clinic_id=clinic.id, first_name="Ficticio", last_name="Paciente"))
    db.commit()
    report = check(db, scratch_dir)
    assert not report.clean
    assert "doctors: 1 filas (se esperaba 0)" in report.problems
    assert "patients: 1 filas (se esperaba 0)" in report.problems


def test_extra_audit_events_and_images_are_reported(db, scratch_dir):
    admin = bootstrap_first(db)
    audit_service.record(db, admin, "patient.created", "patient", 1)
    db.commit()
    (scratch_dir / "ab").mkdir()
    (scratch_dir / "ab" / "foto.jpg").write_bytes(b"x")
    report = check(db, scratch_dir)
    assert "audit_events: 1 eventos que no son del alta inicial" in report.problems
    assert report.image_files == 1 and any("imágenes tiene 1 archivos" in p for p in report.problems)


def test_missing_image_folder_is_reported(db, scratch_dir):
    bootstrap_first(db)
    report = check(db, scratch_dir / "no-existe")
    assert any("no existe" in p for p in report.problems)


def test_command_exit_codes(db, scratch_dir, monkeypatch, capsys):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(scratch_dir))
    assert verify_fresh_install.main([]) == 1  # base vacía: falta el alta
    bootstrap_first(db)
    assert verify_fresh_install.main([]) == 0
    out = capsys.readouterr().out
    assert "Instalación limpia" in out and "admin@definitiva.com" not in out
