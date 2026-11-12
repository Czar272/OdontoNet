"""Carga del modelo y sus metadatos (ODON-269).

El modelo se monta de solo lectura, fuera de Git:
- `AI_MODEL_PATH`: pesos de YOLO11s-seg entrenados en ODON-267 (`best.pt`);
- `AI_MODEL_META`: JSON generado por `research/export_model.py`, con nombre, versión, umbral de
  operación congelado en validación, margen de `uncertain`, cobertura por vista y el SHA-256 que
  deben tener los pesos.

Si los pesos no coinciden con el SHA-256 de los metadatos, el servicio no arranca: un umbral
solo vale para los pesos con que se eligió.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from service.analysis import FDI_PERMANENT, DecisionRules, Detection

MAX_POLYGON_POINTS = 64
THIRD_MOLARS = frozenset({18, 28, 38, 48})


@dataclass(frozen=True)
class ModelInfo:
    name: str
    version: str
    weights_sha256: str
    rules: DecisionRules


class Predictor(Protocol):
    def __call__(self, image_bgr: np.ndarray) -> list[Detection]: ...


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_meta(meta_path: Path, weights_path: Path | None = None) -> ModelInfo:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if weights_path is not None and sha256(weights_path) != meta["weights_sha256"]:
        raise RuntimeError("Los pesos no coinciden con el SHA-256 de AI_MODEL_META")
    rules = DecisionRules(
        threshold=float(meta["threshold"]),
        uncertain_margin=float(meta.get("uncertain_margin", 0.1)),
        coverage={view: frozenset(int(f) for f in fdis) for view, fdis in meta["coverage"].items()},
        # Los terceros molares nunca son `absent` aunque el meta.json no lo diga (especificidad 0,41 en ODON-267).
        never_absent=THIRD_MOLARS | frozenset(int(f) for f in meta.get("never_absent", [])),
    )
    return ModelInfo(meta["model_name"], meta["model_version"], meta["weights_sha256"], rules)


def _simplify(polygon: np.ndarray, width: int, height: int) -> list[list[float]]:
    """Contorno normalizado con 64 puntos como máximo."""
    import cv2

    pts = polygon.astype(np.float32).reshape(-1, 1, 2)
    epsilon = 0.5
    while len(pts) > MAX_POLYGON_POINTS:
        pts = cv2.approxPolyDP(pts, epsilon, True)
        epsilon *= 1.5
    return [[round(float(x) / width, 4), round(float(y) / height, 4)] for x, y in pts.reshape(-1, 2)]


class YoloPredictor:
    """YOLO11s-seg en CPU. Las detecciones bajo `floor` se descartan antes de decidir."""

    def __init__(self, weights_path: Path, floor: float = 0.05, imgsz: int = 640):
        from ultralytics import YOLO

        self.net = YOLO(str(weights_path))
        self.floor, self.imgsz = floor, imgsz

    def __call__(self, image_bgr: np.ndarray) -> list[Detection]:
        result = self.net.predict(image_bgr, conf=self.floor, imgsz=self.imgsz, device="cpu", verbose=False)[0]
        h, w = image_bgr.shape[:2]
        if result.masks is None:
            return []
        out = []
        for cls, conf, box, poly in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist(),
                                        result.boxes.xyxy.tolist(), result.masks.xy):
            if len(poly) < 3:
                continue
            x1, y1, x2, y2 = box
            out.append(Detection(
                fdi=FDI_PERMANENT[int(cls)], confidence=round(float(conf), 4),
                bbox=[round(x1 / w, 4), round(y1 / h, 4), round(x2 / w, 4), round(y2 / h, 4)],
                polygon=_simplify(np.asarray(poly), w, h),
            ))
        return out
