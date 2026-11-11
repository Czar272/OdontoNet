"""Auditoría de IOP-Compass (ODON-266): qué trae el dataset, sin copiar imágenes.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.audit_iop --root ../../Datasets_Odontonet/IOP-Compass/IOP-Compass --out results/auditoria-iop.json

El resultado solo contiene conteos e ids públicos de paciente del dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from research.iop_dataset import FDI_PERMANENT, THIRD_MOLARS, VIEW_TOKENS, discover


def annotations_fingerprint(root: Path) -> str:
    """Huella de la versión de las anotaciones, reproducible tras volver a descargar el dataset.

    SHA-256 de la secuencia, ordenada por ruta relativa POSIX (UTF-8), de:
    ruta relativa en UTF-8 + byte 0x00 + SHA-256 (32 bytes) del contenido del JSON.
    """
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.json"), key=lambda p: p.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\x00")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def label_consistency(records) -> dict:
    """Comprobación geométrica de las etiquetas FDI, independiente del entrenamiento.

    En la vista frontal la pieza 11 (derecha del paciente) debe quedar a la izquierda de la 21 en
    la imagen, y la 11 por encima de la 41. Mide en qué proporción de fotos se cumple.
    """
    from statistics import mean

    left_right = above_below = n_lr = n_ab = 0
    for r in records:
        if r.view != "frontal":
            continue
        cx = {}
        for t in r.teeth:
            if t.fdi in (11, 21, 41) and t.contours:
                pts = max(t.contours, key=len)
                cx[t.fdi] = (mean(p[0] for p in pts), mean(p[1] for p in pts))
        if 11 in cx and 21 in cx:
            n_lr += 1
            left_right += cx[11][0] < cx[21][0]
        if 11 in cx and 41 in cx:
            n_ab += 1
            above_below += cx[11][1] < cx[41][1]
    return {
        "frontal_11_left_of_21_in_image": {"photos": n_lr, "share": round(left_right / n_lr, 4) if n_lr else None},
        "frontal_11_above_41": {"photos": n_ab, "share": round(above_below / n_ab, 4) if n_ab else None},
    }


def audit(root: Path) -> dict:
    records = discover(root)
    patients = sorted({r.patient_id for r in records})
    views = Counter()
    missing_image = Counter()
    missing_annotation = Counter()
    instances_per_view = Counter()
    fdi_counts = Counter()
    unlabeled = Counter()
    multi_contour = 0
    no_contour = 0
    present_by_patient: dict[str, set[int]] = defaultdict(set)
    quadrants_by_view: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        if r.image is None:
            missing_image[r.view] += 1
        if r.annotation is None:
            missing_annotation[r.view] += 1
            continue
        views[r.view] += 1
        instances_per_view[r.view] += len(r.teeth)
        for t in r.teeth:
            if not t.contours:
                no_contour += 1
            elif len(t.contours) > 1:
                multi_contour += 1
            if t.fdi is None:
                unlabeled[t.raw_label or "<vacío>"] += 1
            else:
                fdi_counts[t.fdi] += 1
                quadrants_by_view[r.view][t.fdi // 10] += 1
                present_by_patient[r.patient_id].add(t.fdi)
    teeth_per_patient = [len(present_by_patient[p]) for p in patients]
    absent_positions = sum(32 - n for n in teeth_per_patient)
    third_molar_patients = sum(1 for p in patients if present_by_patient[p] & set(THIRD_MOLARS))
    return {
        "root_name": root.name,
        "patients": len(patients),
        "annotated_views": dict(views),
        "missing_image_by_view": dict(missing_image),
        "missing_annotation_by_view": dict(missing_annotation),
        "instances_by_view": dict(instances_per_view),
        "instances_by_fdi": {str(f): fdi_counts.get(f, 0) for f in FDI_PERMANENT},
        "unlabeled_or_non_permanent_labels": dict(unlabeled.most_common(30)),
        "instances_without_polygon": no_contour,
        "instances_with_several_polygons": multi_contour,
        "patients_with_any_third_molar_visible": third_molar_patients,
        "teeth_visible_per_patient": {
            "min": min(teeth_per_patient, default=0),
            "max": max(teeth_per_patient, default=0),
            "mean": round(sum(teeth_per_patient) / len(teeth_per_patient), 2) if teeth_per_patient else 0,
        },
        "positions_not_visible_in_any_view": absent_positions,
        "view_tokens": VIEW_TOKENS,
        "quadrant_share_by_view": {
            v: {str(q): round(c[q] / sum(c.values()), 3) for q in (1, 2, 3, 4)} for v, c in quadrants_by_view.items()
        },
        "label_consistency": label_consistency(records),
        "annotations_sha256": annotations_fingerprint(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = audit(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("patients", "annotated_views", "instances_without_polygon")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
