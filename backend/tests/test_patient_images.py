"""Almacenamiento privado de imágenes clínicas (ODON-166).

Las imágenes de prueba son bytes generados en memoria: ninguna fotografía real
entra al repositorio. La validación del contenido llega en ODON-170.
"""
import hashlib
import logging
import os
import stat
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.auth.security import hash_password
from app.main import app
from app.models import Patient, PatientImage, User
from app.services import patient_image_service as service
from app.services.image_storage import (
    KEY_PATTERN,
    InvalidStorageKey,
    LocalImageStorage,
    StoredImageNotFound,
)
from scripts.verify_images import verify
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.images]

YESTERDAY = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
JPEG = b"\xff\xd8\xff\xe0" + os.urandom(2048)


@pytest.fixture
def setup(db, client, image_storage):
    clinic, doctor_user, doctor = create_clinic_with_doctor(db, "Clinica Imagenes", "doc@imagenes-clinica.com")
    other_clinic, other_user, _ = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-imagenes.com")
    db.add_all([
        User(name="Admin Img", email="admin@imagenes-clinica.com", hashed_password=hash_password(PASSWORD), role="admin", clinic_id=clinic.id),
        User(name="Recepción", email="recepcion@imagenes-clinica.com", hashed_password=hash_password(PASSWORD), role="receptionist", clinic_id=clinic.id),
    ])
    patient = Patient(first_name="Rosa", last_name="Vega", clinic_id=clinic.id)
    sibling = Patient(first_name="Otro", last_name="Paciente", clinic_id=clinic.id)
    other = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([patient, sibling, other])
    db.commit()

    headers = {
        "doctor": auth_headers(client, "doc@imagenes-clinica.com"),
        "admin": auth_headers(client, "admin@imagenes-clinica.com"),
        "receptionist": auth_headers(client, "recepcion@imagenes-clinica.com"),
        "other": auth_headers(client, "doc@ajena-imagenes.com"),
    }

    def visit(patient_id):
        body = {"visit_at": YESTERDAY.isoformat(), "doctor_id": doctor.id, "reason": "Control"}
        response = client.post(f"/patients/{patient_id}/visits", json=body, headers=headers["doctor"])
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return {
        "db": db,
        "storage": image_storage,
        "patient": patient,
        "sibling": sibling,
        "other": other,
        "doctor_user": doctor_user,
        "other_user": other_user,
        "headers": headers,
        "visit": visit(patient.id),
        "sibling_visit": visit(sibling.id),
    }


def store(setup, patient=None, data=JPEG, content_type="image/jpeg", **extra):
    return service.store_image(
        setup["db"],
        setup["storage"],
        patient or setup["patient"],
        data,
        content_type,
        width=640,
        height=480,
        author=extra.pop("author", setup["doctor_user"]),
        **extra,
    )


def file_url(patient_id, image_id):
    return f"/patients/{patient_id}/images/{image_id}/file"


# --- Almacenamiento local -------------------------------------------------


def test_save_uses_random_key_without_patient_data(scratch_dir):
    storage = LocalImageStorage(scratch_dir)
    key = storage.save(7, b"abc", "jpg")

    assert KEY_PATTERN.fullmatch(key)
    assert key.startswith("7/")
    assert storage.read(key) == b"abc"
    assert storage.keys() == [key]
    assert not list(scratch_dir.rglob("*.tmp"))


@pytest.mark.skipif(os.name != "posix", reason="Permisos POSIX")
def test_saved_file_is_private(scratch_dir):
    storage = LocalImageStorage(scratch_dir)
    key = storage.save(1, b"abc", "png")

    assert stat.S_IMODE((scratch_dir / key).stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "key",
    [
        "../secreto.jpg",
        "1/2026/11/../../../secreto.jpg",
        "/etc/passwd",
        "1/2026/11/" + "A" * 32 + ".jpg",
        "1/2026/11/" + "a" * 32 + ".gif",
        "0/2026/11/" + "a" * 32 + ".jpg",
    ],
)
def test_rejects_keys_outside_the_storage(scratch_dir, key):
    storage = LocalImageStorage(scratch_dir)
    with pytest.raises(InvalidStorageKey):
        storage.read(key)


def test_read_missing_file(scratch_dir):
    storage = LocalImageStorage(scratch_dir)
    with pytest.raises(StoredImageNotFound):
        storage.read("1/2026/11/" + "a" * 32 + ".jpg")


def test_interrupted_write_leaves_nothing(scratch_dir, monkeypatch):
    storage = LocalImageStorage(scratch_dir)

    def broken_replace(*_):
        raise OSError("disco lleno")

    monkeypatch.setattr("app.services.image_storage.os.replace", broken_replace)
    with pytest.raises(OSError):
        storage.save(1, b"abc", "jpg")
    assert [p for p in scratch_dir.rglob("*") if p.is_file()] == []


# --- Registro de imágenes -------------------------------------------------


def test_store_image_records_metadata(setup):
    image = store(setup, clinical_visit_id=setup["visit"], tooth=36)

    assert image.clinic_id == setup["patient"].clinic_id
    assert image.patient_id == setup["patient"].id
    assert image.clinical_visit_id == setup["visit"]
    assert image.tooth == 36
    assert image.size_bytes == len(JPEG)
    assert image.sha256 == hashlib.sha256(JPEG).hexdigest()
    assert image.uploaded_by_user_id == setup["doctor_user"].id
    assert image.uploaded_at is not None
    assert image.storage_key.startswith(f"{image.clinic_id}/")
    assert setup["storage"].read(image.storage_key) == JPEG


@pytest.mark.parametrize(
    "kwargs, status, message",
    [
        ({"content_type": "image/gif"}, 415, "JPEG, PNG o WebP"),
        ({"data": b""}, 422, "vacía"),
        ({"tooth": 19}, 422, "pieza dental"),
        ({"tooth": 86}, 422, "pieza dental"),
    ],
)
def test_store_image_rejects_invalid_input(setup, kwargs, status, message):
    with pytest.raises(HTTPException) as exc:
        store(setup, **kwargs)

    assert exc.value.status_code == status
    assert message in exc.value.detail
    assert setup["storage"].keys() == []


def test_store_image_enforces_size_limit(setup, monkeypatch):
    monkeypatch.setenv("IMAGE_MAX_MB", "1")
    with pytest.raises(HTTPException) as exc:
        store(setup, data=b"\xff" * (1024 * 1024 + 1))

    assert exc.value.status_code == 413
    assert "1 MB" in exc.value.detail
    assert setup["storage"].keys() == []


def test_store_image_rejects_visit_of_another_patient(setup):
    with pytest.raises(HTTPException) as exc:
        store(setup, clinical_visit_id=setup["sibling_visit"])

    assert exc.value.status_code == 422
    assert "no pertenece" in exc.value.detail


def test_store_image_rejects_voided_visit(setup, client):
    response = client.post(
        f"/patients/{setup['patient'].id}/visits/{setup['visit']}/void",
        json={"reason": "Registrada por error"},
        headers=setup["headers"]["doctor"],
    )
    assert response.status_code == 200, response.text

    with pytest.raises(HTTPException) as exc:
        store(setup, clinical_visit_id=setup["visit"])
    assert "anulada" in exc.value.detail


def test_store_image_rejects_archived_patient(setup):
    setup["patient"].archived_at = datetime.now(timezone.utc)
    setup["db"].commit()

    with pytest.raises(HTTPException) as exc:
        store(setup)
    assert exc.value.status_code == 409


def test_database_failure_discards_the_file(setup):
    # Autor de otra clínica: la FK compuesta lo rechaza en la base.
    with pytest.raises(IntegrityError):
        store(setup, author=setup["other_user"])

    assert setup["storage"].keys() == []
    assert setup["db"].query(PatientImage).count() == 0


# --- Descarga por la API --------------------------------------------------


@pytest.mark.parametrize("role", ["doctor", "admin"])
def test_clinical_users_get_the_file(setup, client, role):
    image = store(setup, data=b"\x89PNG\r\n\x1a\n" + b"x" * 100, content_type="image/png")

    response = client.get(file_url(setup["patient"].id, image.id), headers=setup["headers"][role])

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\n" + b"x" * 100
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == f'inline; filename="imagen-{image.id}.png"'


def test_archived_patient_images_remain_readable(setup, client):
    image = store(setup)
    setup["patient"].archived_at = datetime.now(timezone.utc)
    setup["db"].commit()

    response = client.get(file_url(setup["patient"].id, image.id), headers=setup["headers"]["doctor"])
    assert response.status_code == 200


def test_reception_has_no_access(setup, client):
    image = store(setup)
    response = client.get(file_url(setup["patient"].id, image.id), headers=setup["headers"]["receptionist"])
    assert response.status_code == 403


def test_requires_authentication(setup, client):
    image = store(setup)
    assert client.get(file_url(setup["patient"].id, image.id)).status_code == 401


def test_other_clinic_gets_404(setup, client):
    image = store(setup)

    # Ruta del paciente ajeno y ruta de su propio paciente con el id ajeno.
    assert client.get(file_url(setup["patient"].id, image.id), headers=setup["headers"]["other"]).status_code == 404
    assert client.get(file_url(setup["other"].id, image.id), headers=setup["headers"]["other"]).status_code == 404


def test_image_of_another_patient_gets_404(setup, client):
    image = store(setup)
    response = client.get(file_url(setup["sibling"].id, image.id), headers=setup["headers"]["doctor"])

    assert response.status_code == 404
    assert response.json()["detail"] == "Imagen no encontrada."


def test_missing_file_is_reported(setup, client, caplog):
    image = store(setup)
    (setup["storage"].root / image.storage_key).unlink()

    with caplog.at_level(logging.ERROR):
        response = client.get(file_url(setup["patient"].id, image.id), headers=setup["headers"]["doctor"])

    assert response.status_code == 404
    assert "no está disponible" in response.json()["detail"]
    assert f"image_id={image.id}" in caplog.text


def test_no_public_route_serves_stored_files(setup, client):
    image = store(setup)

    assert not [r for r in app.routes if type(r).__name__ == "Mount"]
    for path in (f"/{image.storage_key}", f"/storage/images/{image.storage_key}", f"/images/{image.storage_key}"):
        assert client.get(path, headers=setup["headers"]["doctor"]).status_code == 404


# --- Verificación de respaldos -------------------------------------------


def test_verify_reports_a_consistent_storage(setup):
    store(setup)
    store(setup, patient=setup["sibling"])

    report = verify(setup["db"], setup["storage"])
    assert report.ok
    assert report.checked == 2


def test_verify_detects_every_kind_of_difference(setup):
    missing = store(setup)
    altered = store(setup)
    store(setup)
    root = setup["storage"].root

    (root / missing.storage_key).unlink()
    (root / altered.storage_key).write_bytes(b"otro contenido")
    orphan = setup["storage"].save(setup["patient"].clinic_id, b"sin registro", "jpg")
    (root / "1" / ".resto.jpg.tmp").parent.mkdir(parents=True, exist_ok=True)
    (root / "1" / ".resto.jpg.tmp").write_bytes(b"x")

    report = verify(setup["db"], setup["storage"])

    assert not report.ok
    assert report.checked == 3
    assert report.missing == [f"imagen {missing.id}: {missing.storage_key}"]
    assert report.altered == [f"imagen {altered.id}: {altered.storage_key}"]
    assert report.orphans == [orphan]
    assert report.foreign == ["1/.resto.jpg.tmp"]
