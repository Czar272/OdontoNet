"""Lógica pura del análisis: calidad de cada foto y resultado por pieza (sin modelo ni red).

Regla de seguridad (ODON-269): una pieza no detectada **nunca** se informa como `absent` si
ninguna foto usable de una vista que normalmente la muestra la cubre; entonces es `uncertain`.
`absent` significa «no visible donde la zona sí se ve», nunca «ausente confirmada».
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

FDI_PERMANENT = tuple(q * 10 + n for q in (1, 2, 3, 4) for n in range(1, 9))
VIEWS = ("frontal", "right_lateral", "left_lateral", "upper_occlusal", "lower_occlusal", "detail", "other")


@dataclass(frozen=True)
class QualityRules:
    min_side_px: int = 320
    min_sharpness: float = 15.0  # varianza del laplaciano a 512 px de lado mayor
    min_brightness: float = 35.0
    max_brightness: float = 235.0


@dataclass
class Detection:
    fdi: int
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] normalizados a 0–1
    polygon: list[list[float]]  # contorno normalizado, 64 puntos como máximo


@dataclass
class ImageResult:
    index: int
    view: str
    width: int
    height: int
    usable: bool
    reasons: list[str] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)


def assess_quality(image_bgr: np.ndarray, rules: QualityRules = QualityRules()) -> list[str]:
    """Motivos por los que la foto no sirve; lista vacía si es usable (antes de ver los dientes)."""
    h, w = image_bgr.shape[:2]
    reasons = []
    if min(h, w) < rules.min_side_px:
        reasons.append("too_small")
    scale = 512 / max(h, w)
    small = cv2.resize(image_bgr, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < rules.min_sharpness:
        reasons.append("blurred")
    brightness = float(gray.mean())
    if brightness < rules.min_brightness:
        reasons.append("too_dark")
    elif brightness > rules.max_brightness:
        reasons.append("too_bright")
    return reasons


@dataclass(frozen=True)
class DecisionRules:
    threshold: float  # umbral de operación congelado en validación (ODON-267)
    uncertain_margin: float  # por debajo del umbral, dentro de este margen, la pieza es `uncertain`
    coverage: dict[str, frozenset[int]]  # piezas que cada vista muestra normalmente
    # Piezas que nunca se sugieren como «no visible» (quedan `uncertain`): los terceros molares,
    # por su especificidad baja medida en ODON-267 (0,41 en prueba).
    never_absent: frozenset[int] = frozenset()


def decide_teeth(images: list[ImageResult], rules: DecisionRules) -> list[dict]:
    """Resultado de las 32 piezas a partir de las fotos usables."""
    usable = [img for img in images if img.usable]
    teeth = []
    for fdi in FDI_PERMANENT:
        scores = [(img.index, max((d.confidence for d in img.detections if d.fdi == fdi), default=0.0)) for img in usable]
        best = max((s for _, s in scores), default=0.0)
        covering = [img.index for img in usable if fdi in rules.coverage.get(img.view, frozenset())]
        if best >= rules.threshold:
            status, confidence = "present", best
            evidence = [i for i, s in scores if s >= rules.threshold]
        elif best >= rules.threshold - rules.uncertain_margin or not covering or fdi in rules.never_absent:
            status, confidence, evidence = "uncertain", best, []
        else:
            status, confidence, evidence = "absent", 1.0 - best, covering
        teeth.append({"fdi": fdi, "status": status, "confidence": round(confidence, 4), "evidence": evidence})
    return teeth
