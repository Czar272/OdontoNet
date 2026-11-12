"""Entrenamiento completo de ODON-267 (YOLO11s-seg o RF-DETR Seg Small) con semilla y fracción de pacientes.

Escribe los pesos en runs/<nombre>/ (fuera de Git) y un registro reproducible en
results/entrenamiento/<nombre>.json: semilla, fracción, pacientes usados, épocas, tiempos,
VRAM, hardware, versiones y SHA-256 de los pesos finales.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.train --model yolo11s-seg --fraction 1.0 --seed 0
    PYTHONUTF8=1 .venv/Scripts/python -m research.train --model rfdetr-seg-small --fraction 1.0 --seed 0

Reglas fijadas (docs/AI_INTEGRATION.md §7.3, Jira ODON-267):
- Solo se usan los conjuntos de entrenamiento y validación; el de prueba nunca se toca aquí.
- Sin volteo horizontal (el espejo cambia el cuadrante FDI).
- Las fracciones toman subconjuntos anidados de pacientes (research.experiment.nested_subsets).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = AI_DIR / "weights"
RUNS_DIR = AI_DIR / "runs"
DEFAULT_DATA = AI_DIR.parent.parent / "Datasets_Odontonet" / "IOP-Compass-yolo"
DEFAULTS = {
    "yolo11s-seg": {"epochs": 100, "patience": 20, "batch": 8, "imgsz": 640},
    "rfdetr-seg-small": {"epochs": 50, "patience": 10, "batch": 2, "imgsz": 384},
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def subset_yaml(data_dir: Path, fraction: float, seed: int) -> tuple[Path, list[str]]:
    """data.yaml cuyo entrenamiento es la lista de fotos de los pacientes del subconjunto."""
    from research.experiment import nested_subsets

    split = json.loads((data_dir / "split.json").read_text(encoding="utf-8"))["split"]
    if fraction >= 1.0:
        return data_dir / "data.yaml", sorted(split["train"])
    patients = set(nested_subsets(split["train"], [fraction], seed)[fraction])
    images = sorted(p for p in (data_dir / "images" / "train").glob("*.jpg") if p.name.split("_")[0] in patients)
    sub = data_dir / "subsets"
    sub.mkdir(exist_ok=True)
    listing = sub / f"train_f{int(fraction * 100)}_s{seed}.txt"
    listing.write_text("\n".join(p.resolve().as_posix() for p in images) + "\n", encoding="utf-8")
    base = (data_dir / "data.yaml").read_text(encoding="utf-8")
    yaml = sub / f"data_f{int(fraction * 100)}_s{seed}.yaml"
    yaml.write_text(base.replace("train: images/train", f"train: {listing.resolve().as_posix()}"), encoding="utf-8")
    return yaml, sorted(patients)


def train_yolo(name: str, data_yaml: Path, seed: int, cfg: dict) -> Path:
    from ultralytics import YOLO

    model = YOLO(str(WEIGHTS_DIR / "yolo11s-seg.pt"))
    model.train(
        data=str(data_yaml), epochs=cfg["epochs"], patience=cfg["patience"], batch=cfg["batch"], imgsz=cfg["imgsz"],
        seed=seed, deterministic=True, amp=True, device=0, workers=2, fliplr=0.0,
        project=str(RUNS_DIR), name=name, exist_ok=True, plots=False, verbose=False,
    )
    return Path(model.trainer.save_dir) / "weights" / "best.pt"


def train_rfdetr(name: str, data_dir: Path, seed: int, cfg: dict) -> Path:
    import rfdetr

    model = rfdetr.RFDETRSegSmall(pretrain_weights=str(WEIGHTS_DIR / "rf-detr-seg-small.pt"))
    out = RUNS_DIR / name
    model.train(
        dataset_dir=str(data_dir), epochs=cfg["epochs"], batch_size=cfg["batch"], grad_accum_steps=max(1, 8 // cfg["batch"]),
        output_dir=str(out), seed=seed, aug_config={}, early_stopping=True, early_stopping_patience=cfg["patience"],
        tensorboard=False, progress_bar=None, num_workers=2,
    )
    return out / "checkpoint_best_total.pth"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=list(DEFAULTS))
    parser.add_argument("--fraction", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--out", type=Path, default=AI_DIR / "results" / "entrenamiento")
    args = parser.parse_args()

    import torch

    cfg = dict(DEFAULTS[args.model])
    if args.epochs:
        cfg["epochs"] = args.epochs
    name = f"{args.model}-f{int(args.fraction * 100)}-s{args.seed}"
    if args.model.startswith("rfdetr") and args.fraction < 1.0:
        raise SystemExit("RF-DETR solo se entrena al 100 % (decisión de ODON-267)")
    data_yaml, patients = subset_yaml(args.data, args.fraction, args.seed)
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    if args.model.startswith("yolo"):
        best = train_yolo(name, data_yaml, args.seed, cfg)
    else:
        best = train_rfdetr(name, args.data, args.seed, cfg)
    elapsed = time.perf_counter() - start

    import rfdetr
    import ultralytics

    record = {
        "name": name, "model": args.model, "fraction": args.fraction, "seed": args.seed, **cfg,
        "train_patients": len(patients), "train_patient_ids_sha256": hashlib.sha256(",".join(patients).encode()).hexdigest(),
        "split_file_sha256": sha256(args.data / "split.json"),
        "best_weights": best.relative_to(AI_DIR).as_posix(), "best_weights_sha256": sha256(best),
        "seconds_total": round(elapsed), "peak_vram_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
        "gpu": torch.cuda.get_device_name(0), "python": platform.python_version(), "torch": torch.__version__,
        "ultralytics": ultralytics.__version__, "rfdetr": getattr(rfdetr, "__version__", "1.11.2"),
        "horizontal_flip": False, "test_set_used": False,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
