"""Pruebas de la auditoría y la conversión con un dataset sintético mínimo (sin datos reales)."""

import json

import cv2
import numpy as np

from research.audit_iop import annotations_fingerprint, audit, label_consistency
from research.convert_yolo import convert
from research.iop_dataset import ViewRecord, parse_annotation

VIEWS = ("Center", "Left", "Right", "Upper", "Down")


def _make_dataset(root, n_patients=6, width=400, height=200):
    """Pacientes sintéticos con las 5 vistas; en la frontal, la 11 a la izquierda y arriba."""
    for pid in range(1, n_patients + 1):
        folder = root / f"Patient_{pid}"
        folder.mkdir(parents=True)
        for view in VIEWS:
            cv2.imwrite(str(folder / f"IOP_{view}_{pid}.png"), np.zeros((height, width, 3), np.uint8))
            teeth = [
                {"FDI_NUM": "11", "contours": [[[100, 20], [140, 20], [140, 80], [100, 80]]]},
                {"FDI_NUM": "21", "contours": [[[200, 20], [240, 20], [240, 80], [200, 80]]]},
                {"FDI_NUM": "41", "contours": [[[100, 120], [140, 120], [140, 180], [100, 180]]]},
            ]
            (folder / f"IOP_{view}_{pid}.json").write_text(json.dumps({"teeth": teeth}), encoding="utf-8")


def test_convert_splits_by_patient_and_normalizes_with_original_size(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    _make_dataset(src)
    meta = convert(src, out, long_side=100, seed=1, n_val=2, n_test=1, limit=None)
    assert meta["patients"] == {"train": 3, "val": 2, "test": 1}
    assert meta["images"] == {"train": 15, "val": 10, "test": 5}
    # Ningún paciente en dos conjuntos: los nombres de archivo empiezan por el id del paciente.
    owners = {name: {p.name.split("_")[0] for p in (out / "images" / name).iterdir()} for name in ("train", "val", "test")}
    assert not (owners["train"] & owners["val"] or owners["train"] & owners["test"] or owners["val"] & owners["test"])
    # La imagen se reduce, pero las coordenadas se normalizan con el tamaño original (400×200).
    image = cv2.imread(str(next((out / "images" / "test").iterdir())))
    assert max(image.shape[:2]) == 100
    first = next((out / "labels" / "test").iterdir()).read_text().splitlines()[0].split()
    assert first[0] == "0" and first[1:3] == ["0.250000", "0.100000"]  # pieza 11: (100, 20) / (400, 200)
    assert "names:" in (out / "data.yaml").read_text()


def test_fingerprint_changes_when_an_annotation_changes(tmp_path):
    _make_dataset(tmp_path, n_patients=2)
    before = annotations_fingerprint(tmp_path)
    assert before == annotations_fingerprint(tmp_path)
    target = tmp_path / "Patient_1" / "IOP_Center_1.json"
    target.write_text(target.read_text().replace('"11"', '"12"'), encoding="utf-8")
    assert annotations_fingerprint(tmp_path) != before


def test_label_consistency_detects_swapped_sides():
    good = {"teeth": [
        {"fdi": 11, "contours": [[[0, 0], [10, 0], [10, 10]]]},
        {"fdi": 21, "contours": [[[50, 0], [60, 0], [60, 10]]]},
        {"fdi": 41, "contours": [[[0, 50], [10, 50], [10, 60]]]},
    ]}
    swapped = {"teeth": [
        {"fdi": 21, "contours": [[[0, 0], [10, 0], [10, 10]]]},
        {"fdi": 11, "contours": [[[50, 0], [60, 0], [60, 10]]]},
    ]}
    records = [
        ViewRecord("1", "frontal", None, None, parse_annotation(good)),
        ViewRecord("2", "frontal", None, None, parse_annotation(swapped)),
        ViewRecord("3", "upper_occlusal", None, None, parse_annotation(swapped)),  # otra vista: no cuenta
    ]
    result = label_consistency(records)
    assert result["frontal_11_left_of_21_in_image"] == {"photos": 2, "share": 0.5}
    assert result["frontal_11_above_41"] == {"photos": 1, "share": 1.0}


def test_audit_reports_quadrants_and_fingerprint(tmp_path):
    _make_dataset(tmp_path, n_patients=2)
    summary = audit(tmp_path)
    assert summary["patients"] == 2 and summary["instances_without_polygon"] == 0
    assert set(summary["quadrant_share_by_view"]["frontal"]) == {"1", "2", "3", "4"}
    assert len(summary["annotations_sha256"]) == 64
