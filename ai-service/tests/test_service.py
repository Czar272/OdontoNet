"""Pruebas del servicio de inferencia (ODON-269) con un predictor falso e imágenes sintéticas.

Ninguna prueba usa fotos de pacientes ni el modelo real.
"""

import logging
import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from service.analysis import (
    FDI_PERMANENT,
    DecisionRules,
    Detection,
    ImageResult,
    QualityRules,
    assess_quality,
    decide_teeth,
)
from service.main import MAX_BYTES_PER_IMAGE, create_app
from service.model import ModelInfo, load_meta

TOKEN = "t" * 40
FRONTAL = frozenset(f for f in FDI_PERMANENT if f % 10 <= 5)  # incisivos, caninos y premolares
RULES = DecisionRules(threshold=0.5, uncertain_margin=0.1, coverage={"frontal": FRONTAL, "upper_occlusal": frozenset(range(11, 29))})
INFO = ModelInfo("fake-seg", "0.0-test", "0" * 64, RULES)


def textured_image(width=800, height=600, seed=0) -> np.ndarray:
    """Imagen sintética con textura (nítida y de brillo medio), no una boca."""
    rng = np.random.default_rng(seed)
    img = rng.integers(60, 200, (height, width, 3), dtype=np.uint8)
    return cv2.GaussianBlur(img, (3, 3), 0)


def jpeg(image) -> bytes:
    return cv2.imencode(".jpg", image)[1].tobytes()


class FakePredictor:
    """Detecta con alta confianza las piezas indicadas; registra cuántas veces se llamó."""

    def __init__(self, detected=(11, 21), confidence=0.9):
        self.detected, self.confidence, self.calls = detected, confidence, 0

    def __call__(self, image_bgr):
        self.calls += 1
        return [Detection(f, self.confidence, [0.1, 0.1, 0.2, 0.2], [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]) for f in self.detected]


@pytest.fixture
def predictor():
    return FakePredictor()


@pytest.fixture
def client(predictor):
    app = create_app(loader=lambda: (INFO, predictor), token=TOKEN)
    with TestClient(app) as c:
        yield c


def analyze(client, images, views, headers=None, extra=None):
    files = [("images", (f"f{i}.jpg", data, "image/jpeg")) for i, data in enumerate(images)]
    data = {"request_id": str(uuid.uuid4()), "views": views, **(extra or {})}
    return client.post("/v1/analyses/tooth-status", files=files, data=data,
                       headers={"X-Service-Token": TOKEN} if headers is None else headers)


# --- Reglas puras ---------------------------------------------------------------------------

def _image(index, view, detections=(), usable=True):
    return ImageResult(index, view, 800, 600, usable, [] if usable else ["blurred"],
                       [Detection(f, c, [0, 0, 1, 1], []) for f, c in detections])


def test_detected_tooth_is_present_with_its_evidence():
    teeth = {t["fdi"]: t for t in decide_teeth([_image(0, "frontal", [(11, 0.9)])], RULES)}
    assert teeth[11] == {"fdi": 11, "status": "present", "confidence": 0.9, "evidence": [0]}


def test_undetected_tooth_in_a_covering_view_is_absent_not_confirmed():
    teeth = {t["fdi"]: t for t in decide_teeth([_image(0, "frontal", [(11, 0.9)])], RULES)}
    assert teeth[12]["status"] == "absent" and teeth[12]["evidence"] == [0]


def test_undetected_tooth_without_a_covering_view_is_never_absent():
    teeth = {t["fdi"]: t for t in decide_teeth([_image(0, "frontal", [(11, 0.9)])], RULES)}
    assert teeth[36]["status"] == "uncertain"  # la frontal no cubre los molares


def test_unusable_or_unknown_views_never_support_absent():
    images = [_image(0, "frontal", usable=False), _image(1, "other")]
    assert {t["status"] for t in decide_teeth(images, RULES)} == {"uncertain"}


def test_score_just_below_threshold_is_uncertain():
    teeth = {t["fdi"]: t for t in decide_teeth([_image(0, "frontal", [(12, 0.45)])], RULES)}
    assert teeth[12]["status"] == "uncertain"


def test_always_reports_the_32_teeth():
    assert [t["fdi"] for t in decide_teeth([], RULES)] == list(FDI_PERMANENT)


def test_quality_flags_small_dark_and_flat_images():
    assert assess_quality(textured_image()) == []
    assert "too_small" in assess_quality(textured_image(200, 150))
    assert "too_dark" in assess_quality(np.full((600, 800, 3), 10, np.uint8))
    assert "blurred" in assess_quality(np.full((600, 800, 3), 128, np.uint8))
    assert "too_bright" in assess_quality(np.full((600, 800, 3), 250, np.uint8))


# --- API ------------------------------------------------------------------------------------

def test_health_needs_no_token(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_token_is_required_everywhere_but_health(client):
    assert client.get("/v1/model").status_code == 401
    r = analyze(client, [jpeg(textured_image())], ["frontal"], headers={"X-Service-Token": "otro"})
    assert r.status_code == 401 and r.json() == {"detail": "Token de servicio ausente o inválido.", "code": "unauthorized"}


def test_short_token_refuses_to_start():
    with pytest.raises(RuntimeError, match="AI_SERVICE_TOKEN"):
        create_app(loader=lambda: (INFO, FakePredictor()), token="corto")


def test_model_endpoint_follows_contract(client):
    body = client.get("/v1/model", headers={"X-Service-Token": TOKEN}).json()
    assert body["contract_version"] == "1" and body["device"] == "cpu" and len(body["labels"]) == 32
    assert body["model_name"] == "fake-seg" and body["limits"]["max_images"] == 5


def test_analysis_response_follows_contract(client):
    r = analyze(client, [jpeg(textured_image()), jpeg(textured_image(seed=1))], ["frontal", "upper_occlusal"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contract_version"] == "1" and len(body["teeth"]) == 32
    assert body["model"] == {"name": "fake-seg", "version": "0.0-test", "weights_sha256": "0" * 64}
    assert body["images"][0]["quality"] == {"usable": True, "reasons": []}
    det = body["images"][0]["detections"][0]
    assert set(det) == {"fdi", "confidence", "bbox", "polygon"}
    teeth = {t["fdi"]: t for t in body["teeth"]}
    assert teeth[11]["status"] == "present" and teeth[12]["status"] == "absent" and teeth[38]["status"] == "uncertain"


def test_unusable_photo_is_excluded_without_failing(client, predictor):
    r = analyze(client, [jpeg(np.full((600, 800, 3), 128, np.uint8))], ["frontal"])
    assert r.status_code == 200
    assert r.json()["images"][0]["quality"] == {"usable": False, "reasons": ["blurred"]}
    assert predictor.calls == 0  # no se corre el modelo sobre una foto inservible
    assert {t["status"] for t in r.json()["teeth"]} == {"uncertain"}


def test_photo_without_teeth_is_marked(client, predictor):
    predictor.detected = ()
    body = analyze(client, [jpeg(textured_image())], ["frontal"]).json()
    assert body["images"][0]["quality"] == {"usable": False, "reasons": ["no_teeth_detected"]}
    assert {t["status"] for t in body["teeth"]} == {"uncertain"}


@pytest.mark.parametrize(("images", "views", "code"), [
    (0, [], "invalid_request"),
    (6, ["frontal"] * 6, "invalid_request"),
    (2, ["frontal"], "invalid_request"),
    (1, ["selfie"], "invalid_request"),
])
def test_invalid_requests(client, images, views, code):
    r = analyze(client, [jpeg(textured_image())] * images, views)
    assert r.status_code == 400 and r.json()["code"] == code


def test_extra_fields_such_as_patient_ids_are_rejected(client):
    r = analyze(client, [jpeg(textured_image())], ["frontal"], extra={"patient_id": "123"})
    assert r.status_code == 400 and r.json()["code"] == "invalid_request"


def test_request_id_must_be_a_uuid(client):
    files = [("images", ("f.jpg", jpeg(textured_image()), "image/jpeg"))]
    r = client.post("/v1/analyses/tooth-status", files=files, data={"request_id": "paciente-7", "views": ["frontal"]},
                    headers={"X-Service-Token": TOKEN})
    assert r.status_code == 400


def test_non_image_and_oversized_files(client):
    assert analyze(client, [b"no es una imagen"], ["frontal"]).json()["code"] == "unsupported_image"
    png = cv2.imencode(".png", textured_image())[1].tobytes()
    assert analyze(client, [png], ["frontal"]).json() == {"detail": "Las fotos deben enviarse en JPEG.", "code": "unsupported_image"}
    big = analyze(client, [b"x" * (MAX_BYTES_PER_IMAGE + 1)], ["frontal"])
    assert big.status_code == 413 and big.json()["code"] == "image_too_large"
    huge = analyze(client, [jpeg(np.zeros((10, 4100, 3), np.uint8))], ["frontal"])
    assert huge.status_code == 413


def test_service_writes_no_files_and_logs_no_content(client, tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.INFO, logger="odontonet.ai")
    r = analyze(client, [jpeg(textured_image())], ["frontal"])
    assert r.status_code == 200
    assert list(tmp_path.iterdir()) == []
    logged = " ".join(rec.getMessage() for rec in caplog.records)
    assert r.json()["request_id"] in logged and "frontal" not in logged


def test_load_meta_rejects_weights_that_do_not_match(tmp_path):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"pesos")
    meta = tmp_path / "meta.json"
    meta.write_text('{"model_name": "m", "model_version": "1", "weights_sha256": "abc", "threshold": 0.5, "coverage": {}}')
    with pytest.raises(RuntimeError, match="SHA-256"):
        load_meta(meta, weights)
    info = load_meta(meta)
    assert info.rules.threshold == 0.5 and info.rules.uncertain_margin == 0.1
    assert info.rules.never_absent == frozenset({18, 28, 38, 48})  # aunque el meta.json no lo diga


def test_view_coverage_only_counts_patients_who_have_the_tooth():
    from research.export_model import view_coverage

    labels = {
        "1_frontal": {11, 21, 13}, "1_upper_occlusal": {11, 21, 13, 16, 26},
        "2_frontal": {11, 21}, "2_upper_occlusal": {11, 21, 16, 26},  # el paciente 2 no tiene la 13 visible
        "3_frontal": {11}, "3_upper_occlusal": {11, 16},
    }
    cov = view_coverage(labels, min_share=0.5)
    assert cov["frontal"] == [11, 13, 21]  # 13: 1 de 1 paciente que la tiene; 16 nunca en la frontal
    assert cov["upper_occlusal"] == [11, 13, 16, 21, 26]


def test_third_molars_configured_as_never_absent_stay_uncertain():
    rules = DecisionRules(threshold=0.5, uncertain_margin=0.1, coverage={"upper_occlusal": frozenset({18, 17})},
                          never_absent=frozenset({18, 28, 38, 48}))
    teeth = {t["fdi"]: t for t in decide_teeth([_image(0, "upper_occlusal", [(16, 0.9)])], rules)}
    assert teeth[17]["status"] == "absent"  # cubierta y no detectada
    assert teeth[18]["status"] == "uncertain"  # cubierta, no detectada, pero nunca se sugiere como no visible
    detected = {t["fdi"]: t for t in decide_teeth([_image(0, "upper_occlusal", [(18, 0.9)])], rules)}
    assert detected[18]["status"] == "present"  # si se ve, sí se informa presente


def test_load_meta_reads_never_absent(tmp_path):
    meta = tmp_path / "meta.json"
    meta.write_text('{"model_name": "m", "model_version": "1", "weights_sha256": "abc", "threshold": 0.5,'
                    ' "coverage": {}, "never_absent": [18, 48]}')
    assert load_meta(meta).rules.never_absent == frozenset({18, 28, 38, 48})  # siempre los cuatro



def test_health_and_model_are_unavailable_until_the_model_loads(predictor):
    app = create_app(loader=lambda: (INFO, predictor), token=TOKEN)
    client = TestClient(app)  # sin «with»: el lifespan no corre y el modelo no se carga
    assert client.get("/health").status_code == 503 and client.get("/health").json() == {"status": "loading"}
    r = client.get("/v1/model", headers={"X-Service-Token": TOKEN})
    assert r.status_code == 503 and r.json()["code"] == "model_not_ready"


def test_missing_token_header_is_rejected(client):
    r = analyze(client, [jpeg(textured_image())], ["frontal"], headers={})
    assert r.status_code == 401


def test_images_sent_as_text_are_rejected(client):
    data = {"request_id": str(uuid.uuid4()), "views": ["frontal"], "images": "no-es-archivo"}
    r = client.post("/v1/analyses/tooth-status", data=data, headers={"X-Service-Token": TOKEN})
    assert r.status_code == 400 and r.json()["code"] == "invalid_request"


def test_large_photos_stay_in_memory(client, monkeypatch):
    """Una foto de varios MB no se vuelca a un temporal en disco (Starlette lo hace por encima de 1 MB por defecto)."""
    import tempfile

    created = []
    original = tempfile.SpooledTemporaryFile.rollover

    def spy(self):
        created.append(True)
        return original(self)

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", spy)
    rng = np.random.default_rng(1)
    noisy = rng.integers(0, 255, (1536, 2048, 3), dtype=np.uint8)
    big = cv2.imencode(".jpg", noisy, [cv2.IMWRITE_JPEG_QUALITY, 100])[1].tobytes()
    assert len(big) > 2 * 1024 * 1024
    r = analyze(client, [big], ["frontal"])
    assert r.status_code == 200
    assert created == []


def test_declared_body_too_large_is_rejected_before_reading(client):
    r = client.post("/v1/analyses/tooth-status", content=b"x", headers={
        "X-Service-Token": TOKEN, "Content-Type": "multipart/form-data; boundary=x", "Content-Length": str(60 * 1024 * 1024)})
    assert r.status_code == 413
