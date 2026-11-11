"""Entrenamiento corto en la RTX 4050 (6 GB) para comprobar que cabe (ODON-266).

No busca un buen modelo: mide VRAM máxima y tiempo por época con precisión
mixta y lote pequeño. El entrenamiento real es ODON-267.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.train_smoke --model yolo11s-seg --data ../../Datasets_Odontonet/IOP-Compass-yolo/data.yaml --epochs 3 --batch 8
    PYTHONUTF8=1 .venv/Scripts/python -m research.train_smoke --model rfdetr-seg-small --data ../../Datasets_Odontonet/IOP-Compass-yolo --epochs 1 --batch 2

RF-DETR lee el mismo formato YOLO-seg que Ultralytics: ambos usan los mismos archivos y la misma partición.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "weights"
RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def train_yolo(data: Path, epochs: int, batch: int, imgsz: int, fraction: float) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(WEIGHTS_DIR / "yolo11s-seg.pt"))
    model.train(
        data=str(data), epochs=epochs, batch=batch, imgsz=imgsz, amp=True, device=0, workers=2,
        fliplr=0.0,  # el espejo cambia el cuadrante: la etiqueta FDI sería falsa
        fraction=fraction, project=str(RUNS_DIR), name="smoke-yolo11s-seg", exist_ok=True, plots=False, verbose=False,
    )
    import csv

    metrics = getattr(model.trainer, "metrics", {}) or {}
    final = {k: round(float(v), 4) for k, v in metrics.items() if "mAP50" in k}
    per_epoch = []
    csv_path = Path(model.trainer.save_dir) / "results.csv"
    if csv_path.exists():
        for row in csv.DictReader(csv_path.open(encoding="utf-8")):
            row = {k.strip(): v for k, v in row.items()}
            per_epoch.append({k: round(float(row[k]), 4) for k in row if k == "epoch" or "mAP50" in k})
    return {"final": final, "per_epoch": per_epoch}


def train_rfdetr(model_name: str, data: Path, epochs: int, batch: int) -> dict:
    import rfdetr

    cls = {"rfdetr-seg-nano": "RFDETRSegNano", "rfdetr-seg-small": "RFDETRSegSmall"}[model_name]
    weights = WEIGHTS_DIR / f"{model_name.replace('rfdetr', 'rf-detr')}.pt"
    model = getattr(rfdetr, cls)(pretrain_weights=str(weights))
    model.train(
        dataset_dir=str(data), epochs=epochs, batch_size=batch, grad_accum_steps=max(1, 8 // batch),
        output_dir=str(RUNS_DIR / f"smoke-{model_name}"),
        aug_config={},  # sin volteo horizontal: el espejo cambia el cuadrante y la etiqueta FDI sería falsa
        tensorboard=False, progress_bar=None, num_workers=2, checkpoint_interval=1000,
    )
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=["yolo11s-seg", "rfdetr-seg-nano", "rfdetr-seg-small"])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--fraction", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=Path("results/entrenamiento"))
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("No hay GPU CUDA visible")
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    if args.model.startswith("yolo"):
        metrics = train_yolo(args.data, args.epochs, args.batch, args.imgsz, args.fraction)
    else:
        metrics = train_rfdetr(args.model, args.data, args.epochs, args.batch)
    elapsed = time.perf_counter() - start
    result = {
        "model": args.model, "epochs": args.epochs, "batch": args.batch,
        "imgsz": args.imgsz if args.model.startswith("yolo") else {"rfdetr-seg-nano": 312, "rfdetr-seg-small": 384}[args.model],
        "grad_accum_steps": 1 if args.model.startswith("yolo") else max(1, 8 // args.batch), "fraction": args.fraction,
        "amp": True, "gpu": torch.cuda.get_device_name(0),
        "gpu_total_mb": round(torch.cuda.get_device_properties(0).total_memory / 2**20),
        "peak_allocated_mb": round(torch.cuda.max_memory_allocated() / 2**20),
        "peak_reserved_mb": round(torch.cuda.max_memory_reserved() / 2**20),
        "seconds_total": round(elapsed), "seconds_per_epoch": round(elapsed / args.epochs),
        "metrics_smoke_only": metrics,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.model}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
