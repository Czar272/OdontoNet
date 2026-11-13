"""Pruebas del resumen de ODON-267 con reportes sintéticos."""

import json

from research.summarize import comparison, learning_curve, load_reports, markdown, summarize

MAIN = "main_11_47_without_third_molars"


def _report(name, sens, spec, map50, exploratory=False, counts=None):
    presence = {"tp": 8, "fn": 2, "tn": 950, "fp": 40, "sensitivity_not_visible": sens, "specificity": spec,
                "sensitivity_ci95": [sens - 0.1, min(1, sens + 0.1)], "specificity_ci95": [spec - 0.01, min(1, spec + 0.01)]}
    return {
        "name": name, "threshold": 0.4,
        "presence": {MAIN: presence, "third_molars": presence},
        "mask": {"all": {"mask_map50": map50}}, "numbering": {"all": {"numbering_accuracy": 0.9}},
        "criterion": {"met": sens >= 0.8 and spec >= 0.95, "exploratory": exploratory},
        "per_patient_counts": counts or {"1": [1, 0, 27, 0], "2": [0, 1, 26, 1], "3": [1, 0, 26, 1]},
    }


def _write(folder, rep, suffix="-test.json"):
    (folder / f"{rep['name']}{suffix}").write_text(json.dumps(rep), encoding="utf-8")


def test_exploratory_reports_are_ignored(tmp_path):
    _write(tmp_path, _report("yolo11s-seg-f100-s0", 0.9, 0.97, 0.9))
    _write(tmp_path, _report("yolo11s-seg-f100-s1", 0.1, 0.1, 0.1, exploratory=True), suffix="-test-exploratoria.json")
    assert list(load_reports(tmp_path)) == ["yolo11s-seg-f100-s0"]


def test_learning_curve_groups_by_fraction_with_mean_and_sd(tmp_path):
    for seed, m in ((0, 0.80), (1, 0.84)):
        _write(tmp_path, _report(f"yolo11s-seg-f25-s{seed}-e30", 0.7, 0.96, m))
    _write(tmp_path, _report("yolo11s-seg-f100-s0-e30", 0.9, 0.97, 0.92))
    _write(tmp_path, _report("yolo11s-seg-f100-s0", 0.9, 0.97, 0.99))  # modelo principal (89 épocas): no entra en la curva
    _write(tmp_path, _report("rfdetr-seg-small-f100-s0", 0.85, 0.96, 0.88))
    curve = learning_curve(load_reports(tmp_path))
    assert [r["fraction_percent"] for r in curve] == [25, 100]
    assert curve[0]["seeds"] == 2 and curve[0]["mask_map50"]["mean"] == 0.82
    assert curve[1]["mask_map50"] == {"mean": 0.92, "sd": None, "n": 1}  # una sola semilla, sin el modelo principal


def test_comparison_pairs_rfdetr_with_the_yolo_curve_point(tmp_path):
    _write(tmp_path, _report("yolo11s-seg-f100-s0", 0.9, 0.97, 0.99))  # modelo principal: no es el par
    _write(tmp_path, _report("yolo11s-seg-f100-s0-e30", 0.9, 0.97, 0.92))
    _write(tmp_path, _report("rfdetr-seg-small-f100-s0-e20", 0.85, 0.96, 0.88))
    comp = comparison(load_reports(tmp_path))
    assert len(comp["pairs"]) == 1
    pair = comp["pairs"][0]
    assert pair["yolo"]["name"] == "yolo11s-seg-f100-s0-e30" and pair["rfdetr"]["epochs"] == 20
    assert pair["specificity_diff"]["difference"] == 0  # mismos conteos por paciente
    assert pair["mask_map50_diff"] == -0.04
    text = markdown(summarize(tmp_path))
    assert "Anexo exploratorio" in text and "sin afirmar cuál modelo es mejor" in text


def test_without_rfdetr_the_comparison_is_future_work(tmp_path):
    _write(tmp_path, _report("yolo11s-seg-f100-s0-e30", 0.9, 0.97, 0.92))
    assert comparison(load_reports(tmp_path))["pairs"] == []
    assert "trabajo futuro" in markdown(summarize(tmp_path))


def test_summary_marks_criterion_and_markdown(tmp_path):
    _write(tmp_path, _report("yolo11s-seg-f100-s0", 0.9, 0.97, 0.92))
    summary = summarize(tmp_path)
    assert summary["criterion"]["met"] is True
    text = markdown(summary)
    assert "**Resultado: cumple**" in text and "≥ 0,80" in text


def test_summary_without_primary_is_pending(tmp_path):
    summary = summarize(tmp_path)
    assert summary["criterion"] is None
    assert "Pendiente" in markdown(summary)
