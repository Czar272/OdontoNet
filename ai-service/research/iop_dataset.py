"""Lectura de IOP-Compass (ODON-266).

Implementación propia: el repositorio de IOP-Compass no publica licencia de
código, así que solo se tomó de él la descripción del formato.

Estructura esperada (configurable por argumentos):

    <raíz>/Patient_<pid>/IOP_<Vista>_<pid>.png   (o IOP_<Vista>_RawImage_<pid>.png)
    <raíz>/Patient_<pid>/IOP_<Vista>_<pid>.json

Cada JSON trae una lista ``teeth`` con contornos y número FDI, o una lista
``shapes`` al estilo LabelMe. Nada de este módulo escribe en la carpeta del
dataset.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

VIEW_TOKENS = {
    "Center": "frontal",
    "Left": "left_lateral",
    "Right": "right_lateral",
    "Upper": "upper_occlusal",
    "Down": "lower_occlusal",
}
FDI_PERMANENT = tuple(q * 10 + n for q in (1, 2, 3, 4) for n in range(1, 9))
FDI_TO_CLASS = {fdi: i for i, fdi in enumerate(FDI_PERMANENT)}
THIRD_MOLARS = (18, 28, 38, 48)
PATIENT_DIR = re.compile(r"^Patient_(?P<pid>\d+)$")


@dataclass
class Tooth:
    fdi: int | None
    raw_label: str | None
    contours: list[list[tuple[float, float]]]


@dataclass
class ViewRecord:
    patient_id: str
    view: str
    image: Path | None
    annotation: Path | None
    teeth: list[Tooth] = field(default_factory=list)


def parse_fdi(value: Any) -> int | None:
    """Devuelve el FDI permanente (11–48) o None si la etiqueta no lo es."""
    if value is None:
        return None
    match = re.search(r"\d{2}", str(value))
    if not match:
        return None
    fdi = int(match.group())
    return fdi if fdi in FDI_TO_CLASS else None


def _points(raw: Any) -> list[tuple[float, float]]:
    if not raw:
        return []
    if isinstance(raw[0], (int, float)):  # lista plana x1, y1, x2, y2…
        return [(float(raw[i]), float(raw[i + 1])) for i in range(0, len(raw) - 1, 2)]
    return [(float(p[0]), float(p[1])) for p in raw]


def parse_annotation(payload: dict[str, Any]) -> list[Tooth]:
    teeth: list[Tooth] = []
    if isinstance(payload.get("teeth"), list):
        for row in payload["teeth"]:
            contours = [_points(c) for c in (row.get("contours") or [])]
            if not contours and row.get("contour"):
                contours = [_points(row["contour"])]
            raw = row.get("FDI_NUM", row.get("fdi", row.get("label")))
            teeth.append(Tooth(parse_fdi(raw), None if raw is None else str(raw), [c for c in contours if len(c) >= 3]))
    elif isinstance(payload.get("shapes"), list):
        for shape in payload["shapes"]:
            raw = shape.get("label")
            pts = _points(shape.get("points"))
            teeth.append(Tooth(parse_fdi(raw), None if raw is None else str(raw), [pts] if len(pts) >= 3 else []))
    return teeth


def discover(root: Path, load_annotations: bool = True) -> list[ViewRecord]:
    records: list[ViewRecord] = []
    for patient_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        match = PATIENT_DIR.match(patient_dir.name)
        if not match:
            continue
        pid = match.group("pid")
        for token, view in VIEW_TOKENS.items():
            # La descarga de 2026-11 usa IOP_<Vista>_<pid>.png; la configuración del repositorio, ..._RawImage_...
            candidates = (patient_dir / f"IOP_{token}_{pid}.png", patient_dir / f"IOP_{token}_RawImage_{pid}.png")
            image = next((c for c in candidates if c.exists()), None)
            annotation = patient_dir / f"IOP_{token}_{pid}.json"
            record = ViewRecord(pid, view, image, annotation if annotation.exists() else None)
            if load_annotations and record.annotation:
                with record.annotation.open(encoding="utf-8") as fh:
                    record.teeth = parse_annotation(json.load(fh))
            records.append(record)
    return records


def split_patients(patient_ids: Iterable[str], seed: int = 42, n_val: int = 200, n_test: int = 100) -> dict[str, list[str]]:
    """División por paciente, determinista: ningún paciente queda en dos conjuntos."""
    ids = sorted(set(patient_ids))
    rng = random.Random(seed)
    rng.shuffle(ids)
    if n_val + n_test >= len(ids):
        raise ValueError("No quedan pacientes para entrenamiento")
    test, val, train = ids[:n_test], ids[n_test : n_test + n_val], ids[n_test + n_val :]
    return {"train": sorted(train), "val": sorted(val), "test": sorted(test)}


def yolo_segment_line(tooth: Tooth, width: int, height: int) -> str | None:
    """Línea de etiqueta YOLO-seg: clase y el contorno mayor normalizado a 0–1."""
    if tooth.fdi is None or not tooth.contours:
        return None
    contour = max(tooth.contours, key=_area)
    coords: list[str] = []
    for x, y in contour:
        coords.append(f"{min(max(x / width, 0.0), 1.0):.6f}")
        coords.append(f"{min(max(y / height, 0.0), 1.0):.6f}")
    return f"{FDI_TO_CLASS[tooth.fdi]} " + " ".join(coords)


def _area(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0
