"""Pruebas del experimento de ODON-267 con datos sintéticos (sin modelos ni imágenes reales)."""

import numpy as np
import pytest

from research.evaluate import mask_metrics, numbering_accuracy, parse_stem, read_labels, reference_visibility
from research.experiment import (
    MAIN_TEETH,
    Counts,
    bootstrap_ci,
    choose_threshold,
    nested_subsets,
    paired_bootstrap_diff,
    patient_counts,
    patient_scores,
    total,
)


def test_nested_subsets_are_nested_deterministic_and_sized():
    ids = [str(i) for i in range(700)]
    a = nested_subsets(ids, [0.25, 0.5, 0.75, 1.0], seed=3)
    assert [len(a[f]) for f in (0.25, 0.5, 0.75, 1.0)] == [175, 350, 525, 700]
    assert set(a[0.25]) <= set(a[0.5]) <= set(a[0.75]) <= set(a[1.0])
    assert a == nested_subsets(reversed(ids), [0.25, 0.5, 0.75, 1.0], seed=3)
    assert a[0.25] != nested_subsets(ids, [0.25], seed=4)[0.25]
    with pytest.raises(ValueError):
        nested_subsets(ids, [0], seed=0)


def test_patient_scores_keep_max_across_views():
    scores = patient_scores([("1", 11, 0.3), ("1", 11, 0.9), ("1", 21, 0.4), ("2", 11, 0.2)])
    assert scores == {"1": {11: 0.9, 21: 0.4}, "2": {11: 0.2}}


def test_patient_counts_treat_not_visible_as_positive():
    ref = {"1": {11, 21}}  # 12 no está anotada: no visible
    scores = {"1": {11: 0.9, 21: 0.2, 12: 0.1}}
    c = patient_counts(ref, scores, threshold=0.5, teeth=(11, 21, 12))["1"]
    # 11 visible y detectada (tn); 21 visible pero bajo el umbral (fp); 12 no visible y no detectada (tp)
    assert c == Counts(tp=1, fn=0, tn=1, fp=1)
    assert c.sensitivity == 1.0 and c.specificity == 0.5


def test_main_teeth_exclude_third_molars():
    assert len(MAIN_TEETH) == 28 and not {18, 28, 38, 48} & set(MAIN_TEETH)


def test_choose_threshold_maximizes_sensitivity_under_specificity_target():
    ref = {str(p): set(MAIN_TEETH) - {11} for p in range(20)}  # 11 nunca visible
    scores = {str(p): {f: 0.9 for f in MAIN_TEETH} | {11: 0.3} for p in range(20)}
    chosen = choose_threshold(ref, scores)
    assert chosen["met_specificity_target"]
    assert chosen["sensitivity"] == 1.0 and chosen["specificity"] == 1.0
    assert 0.3 < chosen["threshold"] <= 0.9


def test_choose_threshold_falls_back_to_best_specificity():
    ref = {"1": {11}}
    scores = {"1": {11: 0.1, 21: 0.9}}  # el modelo «ve» 21 que no está y apenas ve 11
    chosen = choose_threshold(ref, scores, teeth=(11, 21), specificity_target=0.99)
    assert chosen["specificity"] == 1.0  # umbral bajo: 11 cuenta como visible
    assert chosen["met_specificity_target"] is True or chosen["sensitivity"] == 0.0


def test_bootstrap_ci_contains_point_and_is_deterministic():
    counts = {str(p): Counts(tp=p % 3, fn=1, tn=20, fp=p % 2) for p in range(30)}
    point = total(counts).sensitivity
    lo, hi = bootstrap_ci(counts, "sensitivity", n_boot=500, seed=1)
    assert lo <= point <= hi
    assert (lo, hi) == bootstrap_ci(counts, "sensitivity", n_boot=500, seed=1)


def test_paired_bootstrap_diff_is_zero_for_identical_models():
    counts = {str(p): Counts(tp=1, fn=p % 2, tn=25, fp=p % 3) for p in range(20)}
    diff = paired_bootstrap_diff(counts, counts, "specificity", n_boot=200)
    assert diff["difference"] == 0 and diff["ci95"] == (0, 0)


def test_read_labels_scales_to_pixels_and_maps_fdi(tmp_path):
    label = tmp_path / "1_frontal.txt"
    label.write_text("0 0.1 0.2 0.3 0.2 0.3 0.4\n31 0 0 0.5 0 0.5 0.5\nbad\n", encoding="utf-8")
    items = read_labels(label, width=200, height=100)
    assert [fdi for fdi, _ in items] == [11, 48]
    assert items[0][1] == pytest.approx([20, 20, 60, 20, 60, 40])
    assert read_labels(tmp_path / "missing.txt", 10, 10) == []


def test_parse_stem_and_reference_visibility():
    assert parse_stem("687_upper_occlusal") == ("687", "upper_occlusal")
    ref = reference_visibility({"1_frontal": [(11, [])], "1_upper_occlusal": [(16, [])], "2_frontal": []})
    assert ref == {"1": {11, 16}, "2": set()}  # un paciente sin anotaciones: todas sus piezas «no visibles»


def _square_rle(x, y, size, w=100, h=100):
    from pycocotools import mask as mask_utils

    m = np.zeros((h, w), np.uint8)
    m[y : y + size, x : x + size] = 1
    rle = mask_utils.encode(np.asfortranarray(m))
    rle["counts"] = rle["counts"].decode("ascii")
    return rle


def test_mask_metrics_and_numbering_on_synthetic_squares():
    gt = {"1_frontal": [(11, [10, 10, 40, 10, 40, 40, 10, 40]), (21, [60, 10, 90, 10, 90, 40, 60, 40])]}
    sizes, views = {"1_frontal": (100, 100)}, {"1_frontal": "frontal"}
    perfect = {"1_frontal": [(11, 0.9, _square_rle(10, 10, 30)), (21, 0.8, _square_rle(60, 10, 30))]}
    swapped = {"1_frontal": [(21, 0.9, _square_rle(10, 10, 30)), (11, 0.8, _square_rle(60, 10, 30))]}
    good = mask_metrics(gt, perfect, sizes, views)
    assert good["frontal"]["mask_map50"] > 0.95
    assert mask_metrics(gt, swapped, sizes, views)["frontal"]["mask_map50"] < 0.05
    num = numbering_accuracy(gt, swapped, sizes, views, threshold=0.5)
    assert num["frontal"] == {"found": 2, "correct_number": 0, "annotated": 2, "numbering_accuracy": 0.0, "detection_rate": 1.0}
