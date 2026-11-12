"""Genera los metadatos que el servicio de inferencia necesita junto a los pesos (ODON-269).

Entrada:
- los pesos elegidos en ODON-267;
- el umbral congelado en validación (`results/evaluacion/<nombre>-umbral.json`), que debe ser de
  esos mismos pesos;
- las etiquetas del conjunto de ENTRENAMIENTO, para calcular qué piezas muestra normalmente cada
  vista (cobertura). Una pieza «se ve» en una vista si aparece en al menos `min_share` de las fotos
  de esa vista de los pacientes que la tienen visible en alguna vista.

Salida: `meta.json` junto a los pesos (fuera de Git), con el SHA-256 de los pesos.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.export_model --weights runs/yolo11s-seg-f100-s0/weights/best.pt \
        --frozen results/evaluacion/yolo11s-seg-f100-s0-umbral.json --version 2026.11.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from research.iop_dataset import FDI_PERMANENT

AI_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA = AI_DIR.parent.parent / "Datasets_Odontonet" / "IOP-Compass-yolo"


def view_coverage(labels: dict[str, set[int]], min_share: float = 0.5) -> dict[str, list[int]]:
    """`labels`: {'<paciente>_<vista>': {fdi anotados}} -> {vista: [fdi que la vista muestra normalmente]}."""
    visible_any: dict[str, set[int]] = defaultdict(set)
    for stem, fdis in labels.items():
        visible_any[stem.split("_", 1)[0]].update(fdis)
    seen = defaultdict(lambda: defaultdict(int))
    possible = defaultdict(lambda: defaultdict(int))
    for stem, fdis in labels.items():
        pid, view = stem.split("_", 1)
        for fdi in visible_any[pid]:
            possible[view][fdi] += 1
            seen[view][fdi] += fdi in fdis
    return {view: sorted(f for f in FDI_PERMANENT if possible[view][f] and seen[view][f] / possible[view][f] >= min_share)
            for view in sorted(possible)}


def read_split_labels(label_dir: Path) -> dict[str, set[int]]:
    out = {}
    for path in label_dir.glob("*.txt"):
        out[path.stem] = {FDI_PERMANENT[int(line.split()[0])] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--name", default="yolo11s-seg-iop-teeth")
    parser.add_argument("--margin", type=float, default=0.1)
    parser.add_argument("--min-share", type=float, default=0.5)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()

    weights_hash = hashlib.sha256(args.weights.read_bytes()).hexdigest()
    frozen = json.loads(args.frozen.read_text(encoding="utf-8"))
    if frozen["weights_sha256"] != weights_hash:
        raise SystemExit("El umbral congelado no corresponde a estos pesos")
    coverage = view_coverage(read_split_labels(args.data / "labels" / "train"), args.min_share)
    meta = {
        "model_name": args.name, "model_version": args.version, "weights_sha256": weights_hash,
        "threshold": frozen["threshold"], "uncertain_margin": args.margin, "coverage": coverage,
        "never_absent": [18, 28, 38, 48],
        "never_absent_rule": "Terceros molares siempre `uncertain`: especificidad 0,41 en prueba (ODON-267); decisión del desarrollador del 2026-11-12",
        "coverage_rule": f"pieza visible en ≥ {args.min_share:.0%} de las fotos de la vista (entrenamiento de IOP-Compass)",
        "threshold_rule": frozen.get("rule"), "source_run": frozen.get("name"),
    }
    out = args.weights.parent / "meta.json"
    out.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("model_name", "model_version", "threshold")} | {v: len(f) for v, f in coverage.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
