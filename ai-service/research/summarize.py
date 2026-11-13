"""Resumen de ODON-267: criterio, curva de aprendizaje de YOLO y comparación con RF-DETR.

Lee los reportes de `research/evaluate.py` (results/evaluacion/*-test.json; los marcados como
exploratorios se ignoran) y escribe:
- results/resumen-odon267.json: todas las cifras;
- results/resumen-odon267.md: tablas listas para la ficha del modelo y la tesis.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.summarize
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from research.experiment import Counts, paired_bootstrap_diff

AI_DIR = Path(__file__).resolve().parent.parent
PRIMARY = "yolo11s-seg-f100-s0"
NAME = re.compile(r"^(?P<model>.+?)-f(?P<fraction>\d+)-s(?P<seed>\d+)(?:-e(?P<epochs>\d+))?$")
CURVE_EPOCHS = 30  # la curva usa el mismo presupuesto de épocas en todas las fracciones
MAIN = "main_11_47_without_third_molars"


def load_reports(folder: Path) -> dict[str, dict]:
    reports = {}
    for path in sorted(folder.glob("*-test.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("criterion", {}).get("exploratory"):
            continue
        reports[data["name"]] = data
    return reports


def _mean_sd(values: list[float]) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"mean": None, "sd": None, "n": 0}
    return {"mean": round(statistics.mean(values), 4), "sd": round(statistics.stdev(values), 4) if len(values) > 1 else None,
            "n": len(values)}


def learning_curve(reports: dict[str, dict], model: str = "yolo11s-seg", epochs: int = CURVE_EPOCHS) -> list[dict]:
    by_fraction: dict[int, list[dict]] = defaultdict(list)
    for name, rep in reports.items():
        m = NAME.match(name)
        if m and m["model"] == model and m["epochs"] is not None and int(m["epochs"]) == epochs:
            by_fraction[int(m["fraction"])].append(rep)
    rows = []
    for fraction in sorted(by_fraction):
        reps = by_fraction[fraction]
        rows.append({
            "fraction_percent": fraction,
            "seeds": len(reps),
            "mask_map50": _mean_sd([r["mask"]["all"]["mask_map50"] for r in reps]),
            "numbering_accuracy": _mean_sd([r["numbering"]["all"]["numbering_accuracy"] for r in reps]),
            "sensitivity_not_visible": _mean_sd([r["presence"][MAIN]["sensitivity_not_visible"] for r in reps]),
            "specificity": _mean_sd([r["presence"][MAIN]["specificity"] for r in reps]),
        })
    return rows


def _counts(rep: dict) -> dict[str, Counts]:
    return {p: Counts(*v) for p, v in rep["per_patient_counts"].items()}


def _model_row(name: str, rep: dict, epochs: int | None) -> dict:
    p = rep["presence"]
    return {
        "name": name, "epochs": epochs, "mask_map50": rep["mask"]["all"]["mask_map50"],
        "sensitivity_not_visible": p[MAIN]["sensitivity_not_visible"], "sensitivity_ci95": p[MAIN]["sensitivity_ci95"],
        "specificity": p[MAIN]["specificity"], "specificity_ci95": p[MAIN]["specificity_ci95"],
        "third_molars_specificity": p["third_molars"]["specificity"],
    }


def comparison(reports: dict[str, dict], yolo_epochs: int = CURVE_EPOCHS) -> dict:
    """Anexo exploratorio: RF-DETR al 100 % frente al punto de YOLO al 100 % de la curva (misma semilla).

    La comparación planeada pasó a trabajo futuro el 2026-11-12, antes de ver resultados. Lo que se
    agregue después es descriptivo: 1 semilla y presupuestos de épocas distintos, sin hipótesis de
    superioridad. La diferencia es RF-DETR − YOLO, pareada por paciente.
    """
    pairs = []
    for name in sorted(reports):
        m = NAME.match(name)
        if not m or m["model"] != "rfdetr-seg-small" or int(m["fraction"]) != 100:
            continue
        seed = int(m["seed"])
        yolo_name = f"yolo11s-seg-f100-s{seed}-e{yolo_epochs}"
        y, r = reports.get(yolo_name), reports[name]
        if not y:
            continue
        pairs.append({
            "seed": seed,
            "yolo": _model_row(yolo_name, y, yolo_epochs),
            "rfdetr": _model_row(name, r, int(m["epochs"]) if m["epochs"] else None),
            "sensitivity_diff": paired_bootstrap_diff(_counts(y), _counts(r), "sensitivity", seed=seed),
            "specificity_diff": paired_bootstrap_diff(_counts(y), _counts(r), "specificity", seed=seed),
            "mask_map50_diff": round(r["mask"]["all"]["mask_map50"] - y["mask"]["all"]["mask_map50"], 4),
        })
    return {"pairs": pairs, "note": "Exploratoria, añadida después del cambio de alcance: sin hipótesis de superioridad."}


def _fmt(v, digits=2):
    if v is None:
        return "—"
    return f"{v:.{digits}f}".replace(".", ",")


def _ci(ci):
    return "—" if not ci or ci[0] is None else f"{_fmt(ci[0])}–{_fmt(ci[1])}"


def markdown(summary: dict) -> str:
    lines = ["## Criterio de aceptación (§7.3)", ""]
    crit = summary["criterion"]
    if crit:
        p = crit["presence"]
        lines += [
            f"Modelo `{PRIMARY}`, prueba, piezas 11–47 sin terceros molares, umbral {_fmt(crit['threshold'], 3)} (elegido en validación).",
            "",
            "| Métrica | Valor | IC 95 % | Exigido |",
            "| --- | --- | --- | --- |",
            f"| Sensibilidad de «no visible» | {_fmt(p['sensitivity_not_visible'])} | {_ci(p['sensitivity_ci95'])} | ≥ 0,80 |",
            f"| Especificidad | {_fmt(p['specificity'])} | {_ci(p['specificity_ci95'])} | ≥ 0,95 |",
            "",
            f"**Resultado: {'cumple' if crit['met'] else 'no cumple'}** (TP {p['tp']}, FN {p['fn']}, TN {p['tn']}, FP {p['fp']}).",
            "",
        ]
    else:
        lines += ["Pendiente: falta la evaluación de prueba del modelo principal.", ""]
    lines += [f"## Curva de aprendizaje de YOLO11s-seg ({CURVE_EPOCHS} épocas por corrida; prueba, media ± DE entre semillas)", "",
              "| % de pacientes | Semillas | mAP50 de máscara | Numeración | Sensibilidad «no visible» | Especificidad |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in summary["learning_curve"]:
        cell = lambda k: f"{_fmt(row[k]['mean'])} ± {_fmt(row[k]['sd'])}"  # noqa: E731
        lines.append(f"| {row['fraction_percent']} | {row['seeds']} | {cell('mask_map50')} | {cell('numbering_accuracy')} | "
                     f"{cell('sensitivity_not_visible')} | {cell('specificity')} |")
    lines += ["", "## Anexo exploratorio: RF-DETR Seg Small frente a YOLO11s-seg (100 %, prueba)", ""]
    pairs = summary["comparison"]["pairs"]
    if not pairs:
        lines.append("Sin corrida de RF-DETR evaluada: la comparación es trabajo futuro (decisión del 2026-11-12).")
    else:
        lines += ["Añadido después de pasar la comparación planeada a trabajo futuro: 1 semilla y épocas distintas; "
                  "descriptivo, sin afirmar cuál modelo es mejor.", "",
                  "| Modelo | Épocas | mAP50 de máscara | Sensibilidad «no visible» (IC 95 %) | Especificidad (IC 95 %) | Especificidad terceros molares |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for pair in pairs:
            for key in ("yolo", "rfdetr"):
                row = pair[key]
                lines.append(f"| `{row['name']}` | {row['epochs'] or '—'} | {_fmt(row['mask_map50'])} | "
                             f"{_fmt(row['sensitivity_not_visible'])} ({_ci(row['sensitivity_ci95'])}) | "
                             f"{_fmt(row['specificity'], 3)} ({_ci(row['specificity_ci95'])}) | {_fmt(row['third_molars_specificity'])} |")
        for pair in pairs:
            s, e = pair["sensitivity_diff"], pair["specificity_diff"]
            lines.append(f"\nSemilla {pair['seed']}, RF-DETR − YOLO (pareado por paciente): sensibilidad {_fmt(s['difference'], 3)} "
                         f"(IC 95 % {_ci(s['ci95'])}), especificidad {_fmt(e['difference'], 3)} (IC 95 % {_ci(e['ci95'])}), "
                         f"mAP50 {_fmt(pair['mask_map50_diff'], 3)}.")
    return "\n".join(lines) + "\n"


def summarize(folder: Path) -> dict:
    reports = load_reports(folder)
    primary = reports.get(PRIMARY)
    criterion = None
    if primary:
        criterion = {"threshold": primary["threshold"], "presence": primary["presence"][MAIN],
                     "third_molars": primary["presence"]["third_molars"], "met": primary["criterion"]["met"],
                     "mask_by_view": primary["mask"], "numbering_by_view": primary["numbering"]}
    return {"reports": sorted(reports), "criterion": criterion, "learning_curve": learning_curve(reports),
            "comparison": comparison(reports)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluations", type=Path, default=AI_DIR / "results" / "evaluacion")
    parser.add_argument("--out", type=Path, default=AI_DIR / "results")
    args = parser.parse_args()
    summary = summarize(args.evaluations)
    (args.out / "resumen-odon267.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / "resumen-odon267.md").write_text(markdown(summary), encoding="utf-8")
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows (cp1252) no tiene «≥»
    print(markdown(summary))


if __name__ == "__main__":
    main()
