"""Galería de imágenes clínicas: listado, miniaturas e historial (ODON-174).

Reutiliza los datos y helpers de test_image_upload.py. Todas las imágenes se
generan en memoria.
"""
import io

import pytest
from PIL import Image

from app.models import PatientImage
from scripts.verify_images import verify
from tests.test_image_upload import consented, grant, jpeg, setup, upload  # noqa: F401 (fixtures)

pytestmark = [pytest.mark.images]


def images_url(setup, patient_id=None, suffix=""):
    return f"/patients/{patient_id or setup['patient']}/images{suffix}"


def get(client, setup, path, role="doctor"):
    return client.get(path, headers=setup["headers"][role])


def rgba_png(size=(900, 600)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, (255, 0, 0, 0)).save(out, format="PNG")
    return out.getvalue()


# --- Listado y metadatos --------------------------------------------------


def test_list_is_empty_without_images(consented, client):
    response = get(client, consented, images_url(consented))
    assert response.status_code == 200
    assert response.json() == []


def test_list_newest_first_with_date_and_author(consented, client):
    first = upload(client, consented, jpeg(), tooth=11).json()
    second = upload(client, consented, jpeg(), clinical_visit_id=consented["visit"], role="admin").json()

    items = get(client, consented, images_url(consented)).json()
    assert [i["id"] for i in items] == [second["id"], first["id"]]
    assert items[0]["uploaded_by"]["name"] == "Admin Sub"
    assert items[0]["clinical_visit"]["reason"] == "Fotografías iniciales"
    assert items[1]["tooth"] == 11
    assert items[1]["uploaded_at"]


def test_list_only_includes_the_patient_images(consented, client):
    upload(client, consented, jpeg())
    grant(client, consented, patient_id=consented["sibling"])
    upload(client, consented, jpeg(), patient_id=consented["sibling"])

    assert len(get(client, consented, images_url(consented)).json()) == 1


def test_get_image_metadata(consented, client):
    image = upload(client, consented, jpeg(), tooth=36).json()

    response = get(client, consented, images_url(consented, suffix=f"/{image['id']}"))
    assert response.status_code == 200
    assert response.json() == image


# --- Miniaturas -----------------------------------------------------------


def test_upload_creates_a_private_thumbnail(consented, client):
    body = upload(client, consented, jpeg(size=(1200, 800))).json()
    image = consented["db"].get(PatientImage, body["id"])
    assert image.thumbnail_key and image.thumbnail_key != image.storage_key

    response = get(client, consented, images_url(consented, suffix=f"/{body['id']}/thumbnail"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content == consented["storage"].read(image.thumbnail_key)
    with Image.open(io.BytesIO(response.content)) as thumb:
        assert max(thumb.size) == 320
        assert thumb.size == (320, 213)
        assert len(thumb.getexif()) == 0


def test_thumbnail_of_transparent_png_is_flattened_jpeg(consented, client):
    body = upload(client, consented, rgba_png(), name="foto.png", content_type="image/png").json()

    response = get(client, consented, images_url(consented, suffix=f"/{body['id']}/thumbnail"))
    with Image.open(io.BytesIO(response.content)) as thumb:
        assert thumb.format == "JPEG"
        assert thumb.mode == "RGB"
        assert thumb.getpixel((5, 5)) == (255, 255, 255)


def test_missing_thumbnail_is_generated_once(consented, client):
    body = upload(client, consented, jpeg()).json()
    db = consented["db"]
    image = db.get(PatientImage, body["id"])
    consented["storage"].discard(image.thumbnail_key)
    # Imagen anterior a ODON-174: sin miniatura registrada.
    image.thumbnail_key = None
    db.commit()

    path = images_url(consented, suffix=f"/{body['id']}/thumbnail")
    first = get(client, consented, path)
    assert first.status_code == 200
    db.expire_all()
    key = db.get(PatientImage, body["id"]).thumbnail_key
    assert key is not None

    assert get(client, consented, path).content == first.content
    db.expire_all()
    assert db.get(PatientImage, body["id"]).thumbnail_key == key


def test_thumbnail_file_lost_is_regenerated(consented, client):
    body = upload(client, consented, jpeg()).json()
    db = consented["db"]
    old_key = db.get(PatientImage, body["id"]).thumbnail_key
    consented["storage"].discard(old_key)

    response = get(client, consented, images_url(consented, suffix=f"/{body['id']}/thumbnail"))
    assert response.status_code == 200
    db.expire_all()
    new_key = db.get(PatientImage, body["id"]).thumbnail_key
    assert new_key != old_key
    assert consented["storage"].read(new_key) == response.content


def test_verify_counts_thumbnails_as_registered(consented, client):
    upload(client, consented, jpeg())
    upload(client, consented, jpeg())

    report = verify(consented["db"], consented["storage"])
    assert report.ok, report
    assert report.checked == 2
    assert len(consented["storage"].keys()) == 4


# --- Aislamiento y permisos (ODON-177) ------------------------------------


def _paths(setup, image_id, patient_id=None):
    return [
        images_url(setup, patient_id),
        images_url(setup, patient_id, f"/{image_id}"),
        images_url(setup, patient_id, f"/{image_id}/thumbnail"),
        images_url(setup, patient_id, f"/{image_id}/file"),
    ]


def test_other_clinic_gets_404_everywhere(consented, client):
    image = upload(client, consented, jpeg()).json()

    for path in _paths(consented, image["id"]):
        assert get(client, consented, path, role="other").status_code == 404, path
    # Con su propio paciente y el id de una imagen ajena.
    for path in _paths(consented, image["id"], consented["other"])[1:]:
        assert get(client, consented, path, role="other").status_code == 404, path


def test_image_of_another_patient_in_the_same_clinic_is_404(consented, client):
    image = upload(client, consented, jpeg()).json()

    for path in _paths(consented, image["id"], consented["sibling"])[1:]:
        response = get(client, consented, path)
        assert response.status_code == 404, path
        assert response.json()["detail"] == "Imagen no encontrada."


def test_reception_and_anonymous_have_no_access(consented, client):
    image = upload(client, consented, jpeg()).json()

    for path in _paths(consented, image["id"]):
        assert get(client, consented, path, role="receptionist").status_code == 403, path
        assert client.get(path).status_code == 401, path


def test_archived_patient_gallery_is_readable(consented, client):
    from datetime import datetime, timezone

    from app.models import Patient

    image = upload(client, consented, jpeg()).json()
    patient = consented["db"].get(Patient, consented["patient"])
    patient.archived_at = datetime.now(timezone.utc)
    consented["db"].commit()

    for path in _paths(consented, image["id"]):
        assert get(client, consented, path).status_code == 200, path


# --- Historial cronológico ------------------------------------------------


def test_uploaded_images_appear_in_the_timeline(consented, client):
    image = upload(client, consented, jpeg(), tooth=36, clinical_visit_id=consented["visit"]).json()

    events = get(client, consented, f"/patients/{consented['patient']}/timeline").json()["items"]
    event = next(e for e in events if e["type"] == "image")
    assert event["id"] == f"image.uploaded:{image['id']}"
    assert event["action"] == "uploaded"
    assert event["title"] == "Fotografía clínica (pieza 36)"
    assert event["detail"] == "Consulta: Fotografías iniciales"
    assert event["actor"]["name"] == "Dr. Clinica Subidas"
    assert event["ref_id"] == image["id"]


def test_timeline_can_filter_only_images(consented, client):
    upload(client, consented, jpeg())

    events = get(client, consented, f"/patients/{consented['patient']}/timeline?types=image").json()["items"]
    assert [e["type"] for e in events] == ["image"]
    assert events[0]["title"] == "Fotografía clínica"
    assert events[0]["detail"] is None
