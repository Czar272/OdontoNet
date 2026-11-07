"""Metadatos, versiones, anulación y auditoría de acceso de imágenes (ODON-178).

Reutiliza los datos y helpers de test_image_upload.py. Todas las imágenes se
generan en memoria.
"""
import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.security import hash_password
from app.models import Doctor, ImageAccessLog, Patient, PatientImage, User
from tests.conftest import PASSWORD, auth_headers
from tests.test_image_upload import consented, jpeg, setup, upload  # noqa: F401 (fixtures)

pytestmark = [pytest.mark.images]

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def ctx(consented, client):
    """Imagen subida por el doctor y un colega de la misma clínica."""
    db = consented["db"]
    clinic_id = db.get(Patient, consented["patient"]).clinic_id
    colleague = User(
        name="Dra. Colega", email="colega@subidas-clinica.com", hashed_password=hash_password(PASSWORD),
        role="doctor", clinic_id=clinic_id,
    )
    db.add(colleague)
    db.flush()
    db.add(Doctor(user_id=colleague.id, clinic_id=clinic_id))
    db.commit()
    consented["headers"]["colleague"] = auth_headers(client, "colega@subidas-clinica.com")

    response = upload(client, consented, jpeg(), tooth=36, view="frontal", taken_on=YESTERDAY)
    assert response.status_code == 201, response.text
    consented["image"] = response.json()
    return consented


def url(ctx, suffix="", patient_id=None, image_id=None):
    return f"/patients/{patient_id or ctx['patient']}/images/{image_id or ctx['image']['id']}{suffix}"


def edit(client, ctx, role="doctor", **changes):
    image = ctx["image"]
    body = {
        "base_revision": image["revision"],
        "origin": image["origin"],
        "view": image["view"],
        "taken_on": image["taken_on"],
        "clinical_visit_id": image["clinical_visit"]["id"] if image["clinical_visit"] else None,
        "tooth": image["tooth"],
        **changes,
    }
    return client.patch(url(ctx), json=body, headers=ctx["headers"][role])


def void(client, ctx, role="doctor", reason="Paciente equivocado"):
    return client.post(url(ctx, "/void"), json={"reason": reason}, headers=ctx["headers"][role])


def get(client, ctx, path, role="doctor"):
    return client.get(path, headers=ctx["headers"][role])


# --- Metadatos al subir ---------------------------------------------------


def test_upload_stores_metadata_and_first_revision(ctx, client):
    image = ctx["image"]
    assert (image["origin"], image["view"], image["taken_on"]) == ("phone", "frontal", YESTERDAY)
    assert image["revision"] == 1
    assert image["voided_at"] is None

    revisions = get(client, ctx, url(ctx, "/revisions")).json()
    assert len(revisions) == 1
    assert revisions[0]["revision"] == 1
    assert revisions[0]["origin"] == "phone"
    assert revisions[0]["tooth"] == 36
    assert revisions[0]["edited_by"]["name"] == "Dr. Clinica Subidas"


@pytest.mark.parametrize(
    "form, message",
    [
        ({"origin": None}, "Indica el origen"),
        ({"origin": "satelite"}, "origen de la fotografía no es válido"),
        ({"view": "cenital"}, "tipo de vista no es válido"),
        ({"taken_on": (date.today() + timedelta(days=2)).isoformat()}, "no puede ser futura"),
    ],
)
def test_upload_validates_metadata(consented, client, form, message):
    response = upload(client, consented, jpeg(), **form)

    assert response.status_code == 422, response.text
    assert message in response.json()["detail"]
    assert consented["storage"].keys() == []


def test_view_and_taken_on_are_optional(consented, client):
    body = upload(client, consented, jpeg(), origin="intraoral_camera").json()
    assert (body["origin"], body["view"], body["taken_on"]) == ("intraoral_camera", None, None)


# --- Corrección con revisiones -------------------------------------------


def test_uploader_corrects_metadata_with_history(ctx, client):
    sha_before = ctx["db"].get(PatientImage, ctx["image"]["id"]).sha256

    response = edit(client, ctx, origin="intraoral_camera", view="upper_occlusal", tooth=16,
                    clinical_visit_id=ctx["visit"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert (body["origin"], body["view"], body["tooth"]) == ("intraoral_camera", "upper_occlusal", 16)
    assert body["clinical_visit"]["id"] == ctx["visit"]

    revisions = get(client, ctx, url(ctx, "/revisions")).json()
    assert [r["revision"] for r in revisions] == [2, 1]
    assert revisions[1]["origin"] == "phone"
    assert revisions[1]["tooth"] == 36
    # El archivo no cambia.
    ctx["db"].expire_all()
    assert ctx["db"].get(PatientImage, ctx["image"]["id"]).sha256 == sha_before


def test_saving_without_changes_creates_no_revision(ctx, client):
    assert edit(client, ctx).json()["revision"] == 1
    assert len(get(client, ctx, url(ctx, "/revisions")).json()) == 1


def test_stale_revision_is_409_with_current_revision(ctx, client):
    assert edit(client, ctx, view="detail").status_code == 200

    response = edit(client, ctx, view="other")  # base_revision 1, vigente 2
    assert response.status_code == 409
    assert response.json()["current_revision"] == 2


def test_only_uploader_or_admin_can_correct(ctx, client):
    response = edit(client, ctx, role="colleague", view="detail")
    assert response.status_code == 403
    assert "Solo quien subió la imagen" in response.json()["detail"]
    assert edit(client, ctx, role="admin", view="detail").status_code == 200


@pytest.mark.parametrize(
    "changes, status",
    [
        ({"tooth": 19}, 422),
        ({"origin": None}, 422),
        ({"view": "cenital"}, 422),
        ({"taken_on": (date.today() + timedelta(days=2)).isoformat()}, 422),
    ],
)
def test_correction_is_validated(ctx, client, changes, status):
    assert edit(client, ctx, **changes).status_code == status


def test_correction_rejects_visit_of_another_patient(ctx, client):
    response = edit(client, ctx, clinical_visit_id=ctx["sibling_visit"])
    assert response.status_code == 422
    assert "no pertenece" in response.json()["detail"]


def test_archived_patient_images_cannot_be_corrected_or_voided(ctx, client):
    patient = ctx["db"].get(Patient, ctx["patient"])
    patient.archived_at = datetime.now(timezone.utc)
    ctx["db"].commit()

    assert edit(client, ctx, view="detail").status_code == 409
    assert void(client, ctx).status_code == 409


# --- Anulación ------------------------------------------------------------


def test_void_keeps_the_image_with_reason(ctx, client):
    response = void(client, ctx, reason="  Paciente equivocado  ")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["voided_at"] is not None
    assert body["voided_by"]["name"] == "Dr. Clinica Subidas"
    assert body["void_reason"] == "Paciente equivocado"

    listed = get(client, ctx, f"/patients/{ctx['patient']}/images").json()
    assert [i["id"] for i in listed] == [body["id"]]
    assert get(client, ctx, url(ctx, "/file")).status_code == 200


def test_voided_image_cannot_be_corrected_or_voided_again(ctx, client):
    void(client, ctx)
    assert edit(client, ctx, view="detail").status_code == 409
    assert void(client, ctx).status_code == 409


def test_void_requires_reason_and_permission(ctx, client):
    assert void(client, ctx, reason="   ").status_code == 422
    assert void(client, ctx, role="colleague").status_code == 403
    assert void(client, ctx, role="admin").status_code == 200


def test_void_constraint_in_database(ctx):
    db = ctx["db"]
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE patient_images SET voided_at = now() WHERE id = :id"), {"id": ctx["image"]["id"]})
        db.commit()
    db.rollback()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE patient_images SET origin = 'satelite' WHERE id = :id"), {"id": ctx["image"]["id"]})
        db.commit()
    db.rollback()


# --- Auditoría de acceso --------------------------------------------------


def test_opening_the_original_is_logged(ctx, client):
    get(client, ctx, url(ctx, "/file"))
    get(client, ctx, url(ctx, "/file"), role="admin")
    get(client, ctx, url(ctx, "/thumbnail"))  # las miniaturas no se registran
    get(client, ctx, url(ctx))  # ni los metadatos

    response = get(client, ctx, url(ctx, "/access-log"), role="admin")
    assert response.status_code == 200
    log = response.json()
    assert [entry["user"]["name"] for entry in log] == ["Admin Sub", "Dr. Clinica Subidas"]
    assert all(entry["accessed_at"] for entry in log)


def test_failed_read_is_not_logged(ctx, client):
    image = ctx["db"].get(PatientImage, ctx["image"]["id"])
    ctx["storage"].discard(image.storage_key)

    assert get(client, ctx, url(ctx, "/file")).status_code == 404
    assert ctx["db"].query(ImageAccessLog).count() == 0


def test_access_log_is_admin_only(ctx, client):
    assert get(client, ctx, url(ctx, "/access-log")).status_code == 403
    assert get(client, ctx, url(ctx, "/access-log"), role="receptionist").status_code == 403
    assert get(client, ctx, url(ctx, "/access-log"), role="other").status_code == 403


# --- Aislamiento y permisos de las rutas nuevas ---------------------------


def test_other_clinic_gets_404_on_new_routes(ctx, client):
    other = ctx["other"]
    image_id = ctx["image"]["id"]
    for patient_id in (ctx["patient"], other):
        path = url(ctx, patient_id=patient_id, image_id=image_id)
        body = {"base_revision": 1, "origin": "phone"}
        assert client.patch(path, json=body, headers=ctx["headers"]["other"]).status_code == 404
        assert client.post(f"{path}/void", json={"reason": "x"}, headers=ctx["headers"]["other"]).status_code == 404
        assert get(client, ctx, f"{path}/revisions", role="other").status_code == 404


def test_reception_has_no_access_to_new_routes(ctx, client):
    assert edit(client, ctx, role="receptionist").status_code == 403
    assert void(client, ctx, role="receptionist").status_code == 403
    assert get(client, ctx, url(ctx, "/revisions"), role="receptionist").status_code == 403


# --- Historial cronológico ------------------------------------------------


def test_corrections_and_voids_appear_in_the_timeline(ctx, client):
    edit(client, ctx, tooth=16)
    void(client, ctx)

    events = get(client, ctx, f"/patients/{ctx['patient']}/timeline?types=image").json()["items"]
    by_action = {e["action"]: e for e in events}
    assert set(by_action) == {"uploaded", "edited", "voided"}
    assert by_action["uploaded"]["voided"] is True
    assert by_action["edited"]["title"] == "Datos de fotografía corregidos (pieza 16)"
    assert by_action["edited"]["detail"] == "Revisión 2"
    assert by_action["edited"]["ref_id"] == ctx["image"]["id"]
    assert by_action["voided"]["title"] == "Fotografía anulada (pieza 16)"
    assert by_action["voided"]["detail"] == "Motivo: Paciente equivocado"


def test_hash_of_file_unchanged_after_void(ctx, client):
    image = ctx["db"].get(PatientImage, ctx["image"]["id"])
    void(client, ctx)
    stored = ctx["storage"].read(image.storage_key)
    assert hashlib.sha256(stored).hexdigest() == image.sha256
