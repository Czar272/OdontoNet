"""Subida de imágenes y consentimiento para fotografías (ODON-170).

Todas las imágenes se generan en memoria con Pillow: ninguna fotografía real
entra al repositorio.
"""
import io
from datetime import date, datetime, timedelta, timezone

import pytest
from zoneinfo import ZoneInfo
from PIL import Image, PngImagePlugin
from sqlalchemy.exc import IntegrityError

from app.auth.security import hash_password
from app.models import Patient, PatientImage, PatientPhotoConsent, User
from tests.conftest import PASSWORD, auth_headers, create_clinic_with_doctor

pytestmark = [pytest.mark.images]

YESTERDAY = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)
# «Hoy» en la zona de la clínica (por defecto America/Guatemala): con date.today()
# en UTC, entre las 18:00 y las 24:00 de Guatemala la fecha ya parecía futura.
TODAY = datetime.now(ZoneInfo("America/Guatemala")).date()
GPS_IFD = 0x8825
ORIENTATION = 0x0112


def jpeg(size=(60, 40), orientation=None, gps=True) -> bytes:
    image = Image.new("RGB", size, (200, 120, 90))
    exif = Image.Exif()
    exif[0x010F] = "FabricanteCelular"  # Make
    exif[0x0110] = "ModeloSecreto"  # Model
    if orientation:
        exif[ORIENTATION] = orientation
    if gps:
        exif[GPS_IFD] = {1: "N", 2: (14.0, 37.0, 0.0), 3: "W", 4: (90.0, 31.0, 0.0)}
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif, comment=b"Paciente Rosa Vega")
    return out.getvalue()


def png(size=(50, 30)) -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Rosa Vega")
    out = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(out, format="PNG", pnginfo=info)
    return out.getvalue()


def encode(fmt: str, size=(32, 32), **options) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (1, 2, 3)).save(out, format=fmt, **options)
    return out.getvalue()


@pytest.fixture
def setup(db, client, image_storage):
    clinic, _, doctor = create_clinic_with_doctor(db, "Clinica Subidas", "doc@subidas-clinica.com")
    other_clinic, _, _ = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-subidas.com")
    db.add_all([
        User(name="Admin Sub", email="admin@subidas-clinica.com", hashed_password=hash_password(PASSWORD), role="admin", clinic_id=clinic.id),
        User(name="Recepción", email="recepcion@subidas-clinica.com", hashed_password=hash_password(PASSWORD), role="receptionist", clinic_id=clinic.id),
    ])
    patient = Patient(first_name="Rosa", last_name="Vega", clinic_id=clinic.id)
    sibling = Patient(first_name="Otro", last_name="Paciente", clinic_id=clinic.id)
    other = Patient(first_name="Ajeno", last_name="X", clinic_id=other_clinic.id)
    db.add_all([patient, sibling, other])
    db.commit()

    headers = {
        "doctor": auth_headers(client, "doc@subidas-clinica.com"),
        "admin": auth_headers(client, "admin@subidas-clinica.com"),
        "receptionist": auth_headers(client, "recepcion@subidas-clinica.com"),
        "other": auth_headers(client, "doc@ajena-subidas.com"),
    }
    response = client.post(
        f"/patients/{sibling.id}/visits",
        json={"visit_at": YESTERDAY.isoformat(), "doctor_id": doctor.id, "reason": "Control"},
        headers=headers["doctor"],
    )
    assert response.status_code == 201, response.text
    sibling_visit = response.json()["id"]
    response = client.post(
        f"/patients/{patient.id}/visits",
        json={"visit_at": YESTERDAY.isoformat(), "doctor_id": doctor.id, "reason": "Fotografías iniciales"},
        headers=headers["doctor"],
    )
    return {
        "db": db,
        "storage": image_storage,
        "patient": patient.id,
        "sibling": sibling.id,
        "other": other.id,
        "headers": headers,
        "visit": response.json()["id"],
        "sibling_visit": sibling_visit,
    }


def consent_url(patient_id):
    return f"/patients/{patient_id}/photo-consent"


def grant(client, setup, patient_id=None, role="doctor", **body):
    data = {"granted": True, "signed_on": YESTERDAY.date().isoformat(), **body}
    return client.post(consent_url(patient_id or setup["patient"]), json=data, headers=setup["headers"][role])


def upload(client, setup, data, name="foto.jpg", content_type="image/jpeg", role="doctor", patient_id=None, **form):
    # Origen obligatorio desde ODON-178; origin=None lo omite.
    form = {"origin": "phone", **form}
    return client.post(
        f"/patients/{patient_id or setup['patient']}/images",
        files={"file": (name, data, content_type)},
        data={k: str(v) for k, v in form.items() if v is not None},
        headers=setup["headers"][role],
    )


@pytest.fixture
def consented(setup, client):
    response = grant(client, setup)
    assert response.status_code == 201, response.text
    return setup


# --- Consentimiento -------------------------------------------------------


def test_consent_starts_empty(setup, client):
    response = client.get(consent_url(setup["patient"]), headers=setup["headers"]["doctor"])
    assert response.status_code == 200
    assert response.json() == {"current": None, "history": []}


def test_record_and_revoke_consent_keeps_history(setup, client):
    first = grant(client, setup, research_use=True, notes="Formulario archivado en recepción")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["version"] == 1
    assert body["granted"] is True and body["research_use"] is True
    assert body["recorded_by"]["name"] == "Dr. Clinica Subidas"

    revoked = grant(client, setup, role="admin", granted=False, signed_on=TODAY.isoformat())
    assert revoked.status_code == 201, revoked.text
    assert revoked.json()["version"] == 2

    status = client.get(consent_url(setup["patient"]), headers=setup["headers"]["doctor"]).json()
    assert status["current"]["version"] == 2
    assert status["current"]["granted"] is False
    assert [c["version"] for c in status["history"]] == [2, 1]
    assert status["history"][1]["notes"] == "Formulario archivado en recepción"


def test_research_use_requires_clinical_consent(setup, client):
    response = grant(client, setup, granted=False, research_use=True)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "research_use"


def test_research_use_defaults_to_false(setup, client):
    assert grant(client, setup).json()["research_use"] is False


def test_research_constraint_also_in_database(setup):
    db = setup["db"]
    patient = db.get(Patient, setup["patient"])
    author = db.query(User).filter_by(email="doc@subidas-clinica.com").one()
    db.add(PatientPhotoConsent(
        clinic_id=patient.clinic_id, patient_id=patient.id, version=1, granted=False,
        research_use=True, signed_on=TODAY, recorded_by_user_id=author.id,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_consent_date_cannot_be_in_the_future(setup, client):
    response = grant(client, setup, signed_on=(TODAY + timedelta(days=2)).isoformat())
    assert response.status_code == 422
    assert "futura" in response.json()["detail"]


def test_consent_notes_are_limited(setup, client):
    assert grant(client, setup, notes="   ").json()["notes"] is None
    assert grant(client, setup, notes="x" * 501).status_code == 422


def test_reception_cannot_see_or_record_consent(setup, client):
    assert client.get(consent_url(setup["patient"]), headers=setup["headers"]["receptionist"]).status_code == 403
    assert grant(client, setup, role="receptionist").status_code == 403


def test_consent_of_another_clinic_is_404(setup, client):
    assert client.get(consent_url(setup["patient"]), headers=setup["headers"]["other"]).status_code == 404
    assert grant(client, setup, role="other").status_code == 404


def test_archived_patient_consent_is_read_only(setup, client):
    grant(client, setup)
    patient = setup["db"].get(Patient, setup["patient"])
    patient.archived_at = datetime.now(timezone.utc)
    setup["db"].commit()

    assert grant(client, setup).status_code == 409
    assert client.get(consent_url(setup["patient"]), headers=setup["headers"]["doctor"]).status_code == 200


# --- Subida ---------------------------------------------------------------


def test_upload_strips_metadata_and_applies_orientation(consented, client):
    original = jpeg(size=(60, 40), orientation=6)
    secrets = (b"Exif", b"FabricanteCelular", b"ModeloSecreto", b"Rosa Vega")
    assert all(secret in original for secret in secrets)
    response = upload(client, consented, original, clinical_visit_id=consented["visit"], tooth=36)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "image/jpeg"
    # Orientación 6 = girar 90°: el ancho y el alto se intercambian.
    assert (body["width"], body["height"]) == (40, 60)
    assert body["tooth"] == 36
    assert body["clinical_visit"]["id"] == consented["visit"]
    assert body["uploaded_by"]["name"] == "Dr. Clinica Subidas"

    image = consented["db"].get(PatientImage, body["id"])
    stored = consented["storage"].read(image.storage_key)
    assert image.size_bytes == len(stored) == body["size_bytes"]
    for secret in secrets:
        assert secret not in stored
    with Image.open(io.BytesIO(stored)) as saved:
        assert len(saved.getexif()) == 0
        assert saved.size == (40, 60)


def test_upload_png_drops_text_chunks(consented, client):
    response = upload(client, consented, png(), name="foto.PNG", content_type="image/png")
    assert response.status_code == 201, response.text
    image = consented["db"].get(PatientImage, response.json()["id"])
    stored = consented["storage"].read(image.storage_key)
    assert b"Rosa Vega" in png()
    assert b"Rosa Vega" not in stored
    assert image.content_type == "image/png"


def test_upload_webp(consented, client):
    response = upload(client, consented, encode("WEBP"), name="foto.webp", content_type="image/webp")
    assert response.status_code == 201, response.text
    assert response.json()["content_type"] == "image/webp"


def test_declared_content_type_is_ignored(consented, client):
    # El navegador dice JPEG, pero el contenido real es PNG con extensión .png.
    response = upload(client, consented, png(), name="foto.png", content_type="image/jpeg")
    assert response.status_code == 201
    assert response.json()["content_type"] == "image/png"


def test_upload_records_the_current_consent(consented, client):
    grant(client, consented, notes="Renovado")
    current = client.get(consent_url(consented["patient"]), headers=consented["headers"]["doctor"]).json()["current"]

    response = upload(client, consented, jpeg())
    assert response.json()["consent_id"] == current["id"]


@pytest.mark.parametrize(
    "data, name, message",
    [
        (png(), "foto.jpg", "no coincide"),
        (encode("GIF"), "foto.gif", "JPEG, PNG o WebP"),
        (encode("GIF"), "foto.png", "JPEG, PNG o WebP"),
        (encode("BMP"), "foto.bmp", "JPEG, PNG o WebP"),
        (b"%PDF-1.4 esto no es una imagen", "foto.jpg", "no es una imagen válida"),
        (jpeg()[:200], "foto.jpg", "no es una imagen válida"),
        (jpeg(), "foto", "JPEG, PNG o WebP"),
    ],
)
def test_rejects_invalid_files(consented, client, data, name, message):
    response = upload(client, consented, data, name=name)

    assert response.status_code == 415, response.text
    assert message in response.json()["detail"]
    assert consented["storage"].keys() == []


def test_rejects_animated_images(consented, client):
    out = io.BytesIO()
    frames = [Image.new("RGB", (16, 16), color) for color in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(out, format="WEBP", save_all=True, append_images=frames[1:])

    response = upload(client, consented, out.getvalue(), name="foto.webp")
    assert response.status_code == 415
    assert "animadas" in response.json()["detail"]


def test_rejects_too_many_pixels(consented, client):
    # 8000 × 7000 = 56 MP en un PNG de pocos kilobytes.
    out = io.BytesIO()
    Image.new("1", (8000, 7000)).save(out, format="PNG")

    response = upload(client, consented, out.getvalue(), name="foto.png")
    assert response.status_code == 422
    assert "megapíxeles" in response.json()["detail"]


def test_rejects_files_over_the_size_limit(consented, client, monkeypatch):
    monkeypatch.setenv("IMAGE_MAX_MB", "1")
    data = jpeg() + b"\0" * (1024 * 1024)

    response = upload(client, consented, data)
    assert response.status_code == 413
    assert "1 MB" in response.json()["detail"]
    assert consented["storage"].keys() == []


def test_rejects_empty_file(consented, client):
    response = upload(client, consented, b"")
    assert response.status_code == 422
    assert "vacía" in response.json()["detail"]


def test_requires_current_consent(setup, client):
    response = upload(client, setup, jpeg())
    assert response.status_code == 409
    assert "consentimiento vigente" in response.json()["detail"]

    grant(client, setup)
    grant(client, setup, granted=False)
    assert upload(client, setup, jpeg()).status_code == 409
    assert setup["storage"].keys() == []


def test_rejects_invalid_tooth_and_foreign_visit(consented, client):
    assert upload(client, consented, jpeg(), tooth=19).status_code == 422
    response = upload(client, consented, jpeg(), clinical_visit_id=consented["sibling_visit"])
    assert response.status_code == 422
    assert "no pertenece" in response.json()["detail"]
    assert consented["storage"].keys() == []


def test_archived_patient_cannot_receive_images(consented, client):
    patient = consented["db"].get(Patient, consented["patient"])
    patient.archived_at = datetime.now(timezone.utc)
    consented["db"].commit()

    assert upload(client, consented, jpeg()).status_code == 409


def test_upload_permissions_and_isolation(consented, client):
    assert upload(client, consented, jpeg(), role="receptionist").status_code == 403
    assert upload(client, consented, jpeg(), role="other").status_code == 404
    response = client.post(
        f"/patients/{consented['patient']}/images", files={"file": ("foto.jpg", jpeg(), "image/jpeg")}
    )
    assert response.status_code == 401
    assert upload(client, consented, jpeg(), role="admin").status_code == 201


def test_uploaded_file_can_be_downloaded(consented, client):
    body = upload(client, consented, jpeg()).json()
    response = client.get(f"/patients/{consented['patient']}/images/{body['id']}/file", headers=consented["headers"]["doctor"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) == body["size_bytes"]


def test_missing_file_field_is_422(consented, client):
    response = client.post(f"/patients/{consented['patient']}/images", headers=consented["headers"]["doctor"])
    assert response.status_code == 422
