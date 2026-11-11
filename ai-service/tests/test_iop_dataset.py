"""Pruebas del lector de IOP-Compass con datos sintéticos (sin imágenes reales)."""

import json

import pytest

from research.iop_dataset import (
    FDI_TO_CLASS,
    discover,
    parse_annotation,
    parse_fdi,
    split_patients,
    yolo_segment_line,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(11, 11), ("36", 36), ("FDI 48", 48), ("tooth_21", 21), (19, None), ("55", None), (None, None), ("x", None)],
)
def test_parse_fdi_only_accepts_permanent_teeth(raw, expected):
    assert parse_fdi(raw) == expected


def test_parse_teeth_schema_keeps_contours_and_labels():
    payload = {
        "teeth": [
            {"FDI_NUM": "11", "contours": [[[0, 0], [10, 0], [10, 10]]]},
            {"fdi": 46, "contour": [0, 0, 4, 0, 4, 4]},
            {"label": "?", "contours": [[[0, 0], [1, 1]]]},
        ]
    }
    teeth = parse_annotation(payload)
    assert [t.fdi for t in teeth] == [11, 46, None]
    assert teeth[1].contours == [[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0)]]
    assert teeth[2].contours == []  # menos de 3 puntos no es un polígono


def test_parse_labelme_schema():
    teeth = parse_annotation({"shapes": [{"label": "21", "points": [[1, 1], [5, 1], [5, 5]]}]})
    assert teeth[0].fdi == 21 and len(teeth[0].contours[0]) == 3


def test_yolo_line_uses_largest_contour_and_normalizes():
    payload = {"teeth": [{"fdi": 48, "contours": [[[0, 0], [2, 0], [2, 2]], [[0, 0], [100, 0], [100, 50], [0, 50]]]}]}
    tooth = parse_annotation(payload)[0]
    line = yolo_segment_line(tooth, width=200, height=100)
    parts = line.split()
    assert parts[0] == str(FDI_TO_CLASS[48]) == "31"
    assert parts[1:] == ["0.000000", "0.000000", "0.500000", "0.000000", "0.500000", "0.500000", "0.000000", "0.500000"]


def test_yolo_line_clamps_points_outside_the_image():
    tooth = parse_annotation({"teeth": [{"fdi": 11, "contours": [[[-5, 0], [210, 0], [210, 120]]]}]})[0]
    values = [float(v) for v in yolo_segment_line(tooth, 200, 100).split()[1:]]
    assert min(values) == 0.0 and max(values) == 1.0


def test_yolo_line_skips_unlabeled_teeth():
    tooth = parse_annotation({"teeth": [{"label": "x", "contours": [[[0, 0], [1, 0], [1, 1]]]}]})[0]
    assert yolo_segment_line(tooth, 10, 10) is None


def test_split_is_by_patient_disjoint_and_deterministic():
    ids = [str(i) for i in range(1000)]
    a = split_patients(ids, seed=42)
    b = split_patients(reversed(ids), seed=42)
    assert a == b
    assert {k: len(v) for k, v in a.items()} == {"train": 700, "val": 200, "test": 100}
    assert not (set(a["train"]) & set(a["val"]) or set(a["train"]) & set(a["test"]) or set(a["val"]) & set(a["test"]))


def test_split_rejects_too_few_patients():
    with pytest.raises(ValueError):
        split_patients(["1", "2"], n_val=1, n_test=1)


def test_discover_reads_patient_folders(tmp_path):
    patient = tmp_path / "Patient_7"
    patient.mkdir()
    (patient / "IOP_Center_RawImage_7.png").write_bytes(b"")
    (patient / "IOP_Center_7.json").write_text(json.dumps({"teeth": [{"fdi": 11, "contours": [[[0, 0], [1, 0], [1, 1]]]}]}))
    (tmp_path / "otra_carpeta").mkdir()
    records = discover(tmp_path)
    assert len(records) == 5  # una por vista esperada
    center = next(r for r in records if r.view == "frontal")
    assert center.image is not None and center.teeth[0].fdi == 11
    assert sum(r.annotation is None for r in records) == 4


def test_discover_accepts_image_name_without_rawimage(tmp_path):
    patient = tmp_path / "Patient_3"
    patient.mkdir()
    (patient / "IOP_Upper_3.png").write_bytes(b"")
    (patient / "IOP_Upper_3.json").write_text(json.dumps({"teeth": []}))
    upper = next(r for r in discover(tmp_path) if r.view == "upper_occlusal")
    assert upper.image is not None and upper.image.name == "IOP_Upper_3.png"
