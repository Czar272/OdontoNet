"""Funciones puras del experimento de ODON-267: subconjuntos, presencia por paciente y bootstrap.

No dependen de PyTorch ni de los modelos, para poder probarlas con datos sintéticos.

Definiciones (docs/AI_INTEGRATION.md §7.3):
- Una pieza es «visible» para el modelo si alguna de las 5 vistas del paciente tiene una detección
  de esa pieza con confianza ≥ umbral. Si no, el modelo dice «no visible».
- La referencia es la anotación: visible si la pieza está anotada en alguna vista.
- La clase de interés es «no visible»: sensibilidad = no visibles detectadas como no visibles;
  especificidad = visibles detectadas como visibles.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Mapping

from research.iop_dataset import FDI_PERMANENT, THIRD_MOLARS

MAIN_TEETH = tuple(f for f in FDI_PERMANENT if f not in THIRD_MOLARS)
SPECIFICITY_TARGET = 0.95  # regla del umbral de operación, fijada antes de evaluar


def nested_subsets(patient_ids: Iterable[str], fractions: Iterable[float], seed: int) -> dict[float, list[str]]:
    """Subconjuntos anidados de pacientes: el de 25 % está dentro del de 50 %, y así sucesivamente.

    Con la misma semilla, el orden es siempre el mismo; cada fracción toma un prefijo.
    """
    ids = sorted(set(patient_ids))
    random.Random(seed).shuffle(ids)
    out = {}
    for f in sorted(fractions):
        if not 0 < f <= 1:
            raise ValueError(f"Fracción inválida: {f}")
        out[f] = sorted(ids[: max(1, round(f * len(ids)))])
    return out


def patient_scores(detections: Iterable[tuple[str, int, float]]) -> dict[str, dict[int, float]]:
    """Máxima confianza por (paciente, pieza) a partir de detecciones (paciente, fdi, confianza) de todas las vistas."""
    scores: dict[str, dict[int, float]] = {}
    for pid, fdi, conf in detections:
        teeth = scores.setdefault(pid, {})
        teeth[fdi] = max(conf, teeth.get(fdi, 0.0))
    return scores


@dataclass(frozen=True)
class Counts:
    tp: int  # no visible y el modelo dice no visible
    fn: int  # no visible y el modelo dice visible
    tn: int  # visible y el modelo dice visible
    fp: int  # visible y el modelo dice no visible

    def __add__(self, other: "Counts") -> "Counts":
        return Counts(self.tp + other.tp, self.fn + other.fn, self.tn + other.tn, self.fp + other.fp)

    @property
    def sensitivity(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def specificity(self) -> float | None:
        return self.tn / (self.tn + self.fp) if self.tn + self.fp else None


def patient_counts(
    reference: Mapping[str, set[int]],
    scores: Mapping[str, Mapping[int, float]],
    threshold: float,
    teeth: Iterable[int] = MAIN_TEETH,
) -> dict[str, Counts]:
    """Matriz de confusión de «no visible» por paciente."""
    teeth = tuple(teeth)
    out = {}
    for pid, visible in reference.items():
        s = scores.get(pid, {})
        tp = fn = tn = fp = 0
        for fdi in teeth:
            model_visible = s.get(fdi, 0.0) >= threshold
            if fdi in visible:
                tn += model_visible
                fp += not model_visible
            else:
                tp += not model_visible
                fn += model_visible
        out[pid] = Counts(tp, fn, tn, fp)
    return out


def total(counts: Mapping[str, Counts]) -> Counts:
    result = Counts(0, 0, 0, 0)
    for c in counts.values():
        result = result + c
    return result


def choose_threshold(
    reference: Mapping[str, set[int]],
    scores: Mapping[str, Mapping[int, float]],
    teeth: Iterable[int] = MAIN_TEETH,
    specificity_target: float = SPECIFICITY_TARGET,
) -> dict:
    """Regla fijada antes de evaluar: el umbral con mayor sensibilidad cuya especificidad sea ≥ objetivo.

    Se aplica SOLO sobre validación. Si ningún umbral llega al objetivo, se toma el de mayor
    especificidad (y se informa).
    """
    teeth = tuple(teeth)
    candidates = sorted({round(v, 4) for s in scores.values() for v in s.values()} | {0.0, 1.01})
    best, fallback = None, None
    for t in candidates:
        c = total(patient_counts(reference, scores, t, teeth))
        sens, spec = c.sensitivity or 0.0, c.specificity or 0.0
        row = {"threshold": t, "sensitivity": sens, "specificity": spec}
        if spec >= specificity_target and (best is None or (sens, -t) > (best["sensitivity"], -best["threshold"])):
            best = row
        if fallback is None or (spec, sens) > (fallback["specificity"], fallback["sensitivity"]):
            fallback = row
    chosen = best or fallback
    return {**chosen, "met_specificity_target": best is not None, "specificity_target": specificity_target}


def bootstrap_ci(
    counts: Mapping[str, Counts], metric: str, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float | None, float | None]:
    """IC por percentiles remuestreando pacientes con reemplazo (las piezas de un paciente no son independientes)."""
    pids = sorted(counts)
    rng = random.Random(seed)
    values = []
    for _ in range(n_boot):
        sample = Counts(0, 0, 0, 0)
        for _ in pids:
            sample = sample + counts[rng.choice(pids)]
        v = getattr(sample, metric)
        if v is not None:
            values.append(v)
    if not values:
        return None, None
    values.sort()
    lo = values[int((alpha / 2) * (len(values) - 1))]
    hi = values[int((1 - alpha / 2) * (len(values) - 1))]
    return lo, hi


def paired_bootstrap_diff(
    a: Mapping[str, Counts], b: Mapping[str, Counts], metric: str, n_boot: int = 2000, seed: int = 0
) -> dict:
    """Diferencia b − a de una métrica, remuestreando los mismos pacientes para ambos modelos."""
    pids = sorted(set(a) & set(b))
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        sa = sb = Counts(0, 0, 0, 0)
        for _ in pids:
            p = rng.choice(pids)
            sa, sb = sa + a[p], sb + b[p]
        va, vb = getattr(sa, metric), getattr(sb, metric)
        if va is not None and vb is not None:
            diffs.append(vb - va)
    diffs.sort()
    point_a, point_b = getattr(total({p: a[p] for p in pids}), metric), getattr(total({p: b[p] for p in pids}), metric)
    return {
        "difference": None if point_a is None or point_b is None else point_b - point_a,
        "ci95": (diffs[int(0.025 * (len(diffs) - 1))], diffs[int(0.975 * (len(diffs) - 1))]) if diffs else (None, None),
    }
