"""API del servicio de inferencia, contrato v1 (docs/AI_INTEGRATION.md §3, ODON-269).

Privacidad:
- solo acepta los campos del contrato: un identificador no puede colarse en un campo extra;
- procesa las fotos en memoria: el formulario multipart se mantiene en RAM (sin volcado a un
  temporal en disco) y se cierra al terminar;
- sus logs solo contienen el `request_id`, el número de fotos y el tiempo. Un error inesperado
  se registra con su tipo y su traza, sin el contenido de la petición.

Límites (antes de decodificar): tamaño del cuerpo, 5 archivos, 10 MB por foto, solo JPEG y 4096 px
de lado como máximo, leído de la cabecera de la imagen.

Configuración (variables de entorno):
- AI_SERVICE_TOKEN: secreto compartido con la API clínica (obligatorio, 32 caracteres o más).
- AI_MODEL_PATH / AI_MODEL_META: pesos y metadatos del modelo, montados de solo lectura.
"""

from __future__ import annotations

import hmac
import io
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from PIL import Image
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartParser

from service.analysis import VIEWS, ImageResult, QualityRules, assess_quality, decide_teeth
from service.model import ModelInfo, Predictor, YoloPredictor, load_meta

CONTRACT_VERSION = "1"
MAX_IMAGES = 5
MAX_BYTES_PER_IMAGE = 10 * 1024 * 1024
MAX_SIDE_PX = 4096
MAX_BODY_BYTES = MAX_IMAGES * MAX_BYTES_PER_IMAGE + 64 * 1024  # fotos más los campos de texto
ALLOWED_FIELDS = {"request_id", "images", "views"}

# Starlette vuelca a disco cada archivo de más de 1 MB; el servicio no debe escribir imágenes.
MultiPartParser.spool_max_size = MAX_BYTES_PER_IMAGE + 1

log = logging.getLogger("odontonet.ai")


class ServiceError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail


def _error(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code})


def _default_loader() -> tuple[ModelInfo, Predictor]:
    weights, meta = Path(os.environ["AI_MODEL_PATH"]), Path(os.environ["AI_MODEL_META"])
    return load_meta(meta, weights), YoloPredictor(weights)


def decode_jpeg(data: bytes) -> np.ndarray:
    """Comprueba formato y resolución en la cabecera ANTES de decodificar la imagen completa."""
    if not data:
        raise ServiceError(415, "unsupported_image", "Una foto no es una imagen admitida.")
    try:
        with Image.open(io.BytesIO(data)) as header:
            fmt, (width, height) = header.format, header.size
    except Exception:  # cabecera ilegible
        raise ServiceError(415, "unsupported_image", "Una foto no es una imagen admitida.") from None
    if fmt != "JPEG":
        raise ServiceError(415, "unsupported_image", "Las fotos deben enviarse en JPEG.")
    if max(width, height) > MAX_SIDE_PX:
        raise ServiceError(413, "image_too_large", "Una foto supera la resolución permitida.")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ServiceError(415, "unsupported_image", "Una foto no es una imagen admitida.")
    return image


def create_app(loader: Callable[[], tuple[ModelInfo, Predictor]] = _default_loader,
               token: str | None = None, quality: QualityRules = QualityRules()) -> FastAPI:
    token = token if token is not None else os.environ.get("AI_SERVICE_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("AI_SERVICE_TOKEN debe tener al menos 32 caracteres")
    state: dict = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        state["info"], state["predictor"] = loader()
        yield
        state.clear()

    app = FastAPI(title="OdontoNet AI service", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.exception_handler(ServiceError)
    async def _service_error(_request: Request, exc: ServiceError):
        return _error(exc.status, exc.code, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException):
        # p. ej. un multipart mal formado: mismo formato que el resto de errores del contrato
        if exc.status_code == 404:
            return _error(404, "not_found", "Ruta inexistente.")
        if exc.status_code == 405:
            return _error(405, "method_not_allowed", "Método no permitido.")
        return _error(400, "invalid_request", "La petición no es un formulario válido.")

    def authorize(request: Request) -> None:
        sent = request.headers.get("x-service-token", "")
        if not hmac.compare_digest(sent.encode(), token.encode()):
            raise ServiceError(401, "unauthorized", "Token de servicio ausente o inválido.")

    def ready() -> ModelInfo:
        if "info" not in state:
            raise ServiceError(503, "model_not_ready", "El modelo aún no está cargado.")
        return state["info"]

    @app.get("/health")
    async def health():
        if "info" not in state:
            return JSONResponse(status_code=503, content={"status": "loading"})
        return {"status": "ok"}

    @app.get("/v1/model")
    async def model(request: Request):
        authorize(request)
        info = ready()
        return {
            "contract_version": CONTRACT_VERSION, "model_name": info.name, "model_version": info.version,
            "weights_sha256": info.weights_sha256, "task": "tooth_status",
            "labels": [q * 10 + n for q in (1, 2, 3, 4) for n in range(1, 9)],
            "limits": {"max_images": MAX_IMAGES, "max_bytes_per_image": MAX_BYTES_PER_IMAGE, "max_side_px": MAX_SIDE_PX},
            "device": "cpu",
        }

    def analyze(info: ModelInfo, images: list[np.ndarray], views: list[str]) -> list[ImageResult]:
        """Trabajo de CPU, fuera del bucle de eventos: /health sigue respondiendo durante un análisis."""
        predictor = state["predictor"]
        results = []
        for index, (image, view) in enumerate(zip(images, views)):
            h, w = image.shape[:2]
            reasons = assess_quality(image, quality)
            detections = predictor(image) if not reasons else []
            if not reasons and not detections:
                reasons = ["no_teeth_detected"]
            results.append(ImageResult(index, view, w, h, usable=not reasons, reasons=reasons, detections=detections))
        return results

    @app.post("/v1/analyses/tooth-status")
    async def tooth_status(request: Request):
        authorize(request)
        info = ready()
        started = time.perf_counter()
        try:
            declared = int(request.headers.get("content-length", "0"))
        except ValueError:
            declared = 0
        if declared > MAX_BODY_BYTES:
            raise ServiceError(413, "image_too_large", "La petición supera el tamaño permitido.")
        form = await request.form(max_files=MAX_IMAGES, max_fields=MAX_IMAGES + 2, max_part_size=64 * 1024)
        try:
            if set(form.keys()) - ALLOWED_FIELDS:
                raise ServiceError(400, "invalid_request", "La petición tiene campos que el contrato no admite.")
            try:
                request_id = str(uuid.UUID(str(form.get("request_id", ""))))
            except ValueError:
                raise ServiceError(400, "invalid_request", "request_id debe ser un UUID.") from None
            files, views = form.getlist("images"), [str(v) for v in form.getlist("views")]
            if not 1 <= len(files) <= MAX_IMAGES or len(views) != len(files):
                raise ServiceError(400, "invalid_request", "Se esperan de 1 a 5 fotos y una vista por foto.")
            if any(v not in VIEWS for v in views):
                raise ServiceError(400, "invalid_request", "Vista desconocida.")
            payloads = []
            for upload in files:
                if not hasattr(upload, "read"):
                    raise ServiceError(400, "invalid_request", "images debe contener archivos.")
                data = await upload.read(MAX_BYTES_PER_IMAGE + 1)
                if len(data) > MAX_BYTES_PER_IMAGE:
                    raise ServiceError(413, "image_too_large", "Una foto supera el tamaño permitido.")
                payloads.append(data)
        finally:
            await form.close()

        decoded = [decode_jpeg(data) for data in payloads]
        results = await run_in_threadpool(analyze, info, decoded, views)
        teeth = decide_teeth(results, info.rules)
        elapsed = round((time.perf_counter() - started) * 1000)
        log.info("analysis request_id=%s images=%d elapsed_ms=%d", request_id, len(results), elapsed)
        return {
            "contract_version": CONTRACT_VERSION, "request_id": request_id,
            "model": {"name": info.name, "version": info.version, "weights_sha256": info.weights_sha256},
            "elapsed_ms": elapsed,
            "images": [{
                "index": r.index, "width": r.width, "height": r.height,
                "quality": {"usable": r.usable, "reasons": r.reasons},
                "detections": [{"fdi": d.fdi, "confidence": d.confidence, "bbox": d.bbox, "polygon": d.polygon}
                               for d in r.detections],
            } for r in results],
            "teeth": teeth,
        }

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception):
        log.error("inference_error type=%s", type(exc).__name__)
        return _error(500, "inference_error", "Error interno del servicio de análisis.")

    return app


def app_from_env() -> FastAPI:  # para uvicorn --factory
    return create_app()
