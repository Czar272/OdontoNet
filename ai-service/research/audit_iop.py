"""Auditoría de IOP-Compass (ODON-266): qué trae el dataset, sin copiar imágenes.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.audit_iop --root ../../IOP-Compass/<carpeta> --out results/auditoria-iop.json

El resultado solo contiene conteos e ids públicos de paciente del dataset.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from research.iop_dataset import FDI_PERMANENT, THIRD_MOLARS, VIEW_TOKENS, discover


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
