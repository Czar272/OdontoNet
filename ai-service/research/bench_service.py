"""Tiempo por análisis completo del servicio en CPU (ODON-269), con el modelo real.

Envía al servicio, en proceso y sin red, las 5 vistas de un paciente del conjunto de prueba
de IOP-Compass reducidas a 2048 px (como la copia que manda el backend), y mide el tiempo de
la petición entera: decodificar, controlar calidad, inferir las 5 fotos y decidir por pieza.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.bench_service --model-dir runs/yolo11s-seg-f100-s0/weights \
        --images ../../Datasets_Odontonet/_latencia-real --runs 10 [--threads 2]
"""

from __future__ import annotations

import os
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # equipo sin GPU (en Windows, "" no la oculta)
if "--threads" in sys.argv:
    import psutil as _psutil

    _n = int(sys.argv[sys.argv.index("--threads") + 1])
    _psutil.Process().cpu_affinity(list(range(0, 2 * _n, 2)))
    os.environ["OMP_NUM_THREADS"] = str(_n)

import argparse
import json
import statistics
import time
import uuid
from pathlib import Path

VIEW_OF = {"Center": "frontal", "Left": "left_lateral", "Right": "right_lateral", "Upper": "upper_occlusal", "Down": "lower_occlusal"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path("results/latencia-servicio"))
    args = parser.parse_args()

    import cv2
    import torch
    from fastapi.testclient import TestClient

    if torch.cuda.is_available():
        raise SystemExit("La GPU sigue visible")
    if args.threads:
        import ultralytics.utils as uu
        import ultralytics.utils.torch_utils as tu

        uu.NUM_THREADS = tu.NUM_THREADS = args.threads
        torch.set_num_threads(args.threads)

    from service.main import create_app
    from service.model import YoloPredictor, load_meta

    weights, meta = args.model_dir / "best.pt", args.model_dir / "meta.json"
    app = create_app(loader=lambda: (load_meta(meta, weights), YoloPredictor(weights)), token="b" * 40)
    pid = sorted(p.name.split("_")[-1].split(".")[0] for p in args.images.glob("IOP_Center_*.png"))[0]
    files, views = [], []
    for token, view in VIEW_OF.items():
        img = cv2.imread(str(args.images / f"IOP_{token}_{pid}.png"))
        scale = 2048 / max(img.shape[:2])
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        files.append(("images", (f"{view}.jpg", cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes(), "image/jpeg")))
        views.append(view)
    times = []
    with TestClient(app) as client:
        for i in range(args.runs + 1):
            start = time.perf_counter()
            r = client.post("/v1/analyses/tooth-status", files=files,
                            data={"request_id": str(uuid.uuid4()), "views": views}, headers={"X-Service-Token": "b" * 40})
            elapsed = time.perf_counter() - start
            r.raise_for_status()
            if i:  # la primera es de calentamiento
                times.append(elapsed)
            statuses = [t["status"] for t in r.json()["teeth"]]
    times.sort()
    result = {
        "photos_per_analysis": 5, "runs": args.runs, "threads_limit": args.threads,
        "p50_s": round(statistics.median(times), 2), "p95_s": round(times[min(len(times) - 1, int(0.95 * len(times)))], 2),
        "max_s": round(times[-1], 2), "timeout_s": 120,
        "last_status_counts": {s: statuses.count(s) for s in ("present", "absent", "uncertain")},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.threads}nucleos" if args.threads else ""
    (args.out / f"analisis-5-fotos{suffix}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
