"""Latencia por foto en CPU, con la GPU oculta (ODON-266).

Mide de punta a punta lo que haría el servicio con una foto: preprocesado,
inferencia y posprocesado, a partir de una imagen BGR en memoria.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.bench_cpu --model yolo11s-seg --backend torch --out results/latencia
    .venv/Scripts/python -m research.bench_cpu --model rfdetr-seg-nano --backend onnx --images <carpeta>

Sin --images usa fotos sintéticas de 2048×1536 (el tamaño de la copia que
envía el backend, AI_INTEGRATION.md §2); con --images, fotos reales del
dataset público, reducidas igual.
"""

from __future__ import annotations

import os

import sys

# En Windows, asignar "" borra la variable; "-1" sí oculta la GPU a CUDA.
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # antes de importar torch: equipo sin GPU
if "--threads" in sys.argv:
    # Ultralytics vuelve a fijar los hilos de PyTorch al importarse y su sesión ONNX usa todos los
    # núcleos, así que el límite se impone al proceso entero con afinidad de CPU: N núcleos físicos
    # distintos (en este i7-12650H los lógicos pares 0, 2, 4… son núcleos P diferentes).
    import psutil as _psutil

    _n = int(sys.argv[sys.argv.index("--threads") + 1])
    _psutil.Process().cpu_affinity(list(range(0, 2 * _n, 2)))
    os.environ["OMP_NUM_THREADS"] = str(_n)

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

import numpy as np
import psutil

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "weights"
LONG_SIDE = 2048


def load_images(folder: Path | None, n: int) -> list[np.ndarray]:
    import cv2

    if folder is None:
        rng = np.random.default_rng(0)
        # Fondo suave con manchas claras: evita el caso irreal de ruido puro.
        base = cv2.GaussianBlur(
            rng.integers(0, 255, (1536, 2048, 3), dtype=np.uint8), (0, 0), 25
        )
        return [np.ascontiguousarray(np.roll(base, i * 37, axis=1)) for i in range(n)]
    paths = sorted(
        p for p in folder.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )[:n]
    images = []
    for p in paths:
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        scale = LONG_SIDE / max(img.shape[:2])
        if scale < 1:
            img = cv2.resize(
                img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
            )
        images.append(img)
    if not images:
        raise SystemExit(f"No hay imágenes en {folder}")
    return images


def build_predictor(
    model: str, backend: str, imgsz: int | None, threads: int | None = None
):
    """Devuelve (predict(img_bgr) -> n_detecciones, descripción, archivo de pesos)."""
    if model.startswith("yolo"):
        from ultralytics import YOLO

        if threads:
            # select_device() de Ultralytics vuelve a fijar torch.set_num_threads(NUM_THREADS)
            # en cada predict; NUM_THREADS sale de os.cpu_count(), que ignora la afinidad.
            import ultralytics.utils as _uu
            import ultralytics.utils.torch_utils as _tu

            _uu.NUM_THREADS = _tu.NUM_THREADS = threads
        weights = WEIGHTS_DIR / f"{model}.pt"
        size = imgsz or 640
        net = YOLO(str(weights))
        if backend == "onnx":
            if threads:
                _limit_onnx_threads(threads)
            onnx_path = net.export(
                format="onnx", imgsz=size, dynamic=False, simplify=True, device="cpu"
            )
            net = YOLO(onnx_path, task="segment")
            weights = Path(onnx_path)

        def predict(img):
            res = net.predict(img, imgsz=size, device="cpu", conf=0.25, verbose=False)
            return len(res[0].boxes)

        return predict, {"imgsz": size}, weights

    import rfdetr

    classes = {"rfdetr-seg-nano": "RFDETRSegNano", "rfdetr-seg-small": "RFDETRSegSmall"}
    weights = WEIGHTS_DIR / f"{model.replace('rfdetr', 'rf-detr')}.pt"
    net = getattr(rfdetr, classes[model])(device="cpu", pretrain_weights=str(weights))
    size = getattr(net.model_config, "resolution", None)
    if backend == "onnx":
        return _rfdetr_onnx(net, model, threads), {"imgsz": size}, weights

    def predict(img):
        rgb = img[:, :, ::-1].copy()
        det = net.predict(rgb, threshold=0.25)
        return len(det)

    return predict, {"imgsz": size}, weights


def _limit_onnx_threads(threads: int) -> None:
    """Ultralytics crea su sesión ONNX con todos los núcleos lógicos; con la afinidad limitada
    esos hilos se estorban entre sí. Se fija intra_op al número de núcleos permitidos, como
    haría ONNX Runtime en un equipo que de verdad tuviera esos núcleos."""
    import onnxruntime as ort

    original = ort.InferenceSession

    def session(path, sess_options=None, *args, **kwargs):
        sess_options = sess_options or ort.SessionOptions()
        sess_options.intra_op_num_threads = threads
        sess_options.inter_op_num_threads = 1
        return original(path, sess_options, *args, **kwargs)

    ort.InferenceSession = session


def _rfdetr_onnx(net, model: str, threads: int | None):
    import onnxruntime as ort

    out_dir = WEIGHTS_DIR / f"{model}-onnx"
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_files = list(out_dir.glob("*.onnx"))
    onnx_path = (
        onnx_files[0]
        if onnx_files
        else Path(net.export(output_dir=str(out_dir), verbose=False))
    )
    options = ort.SessionOptions()
    if threads:
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(onnx_path), options, providers=["CPUExecutionProvider"]
    )
    inp = session.get_inputs()[0]
    _, _, h, w = inp.shape
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def predict(img):
        import cv2

        x = (
            cv2.resize(img[:, :, ::-1], (w, h), interpolation=cv2.INTER_LINEAR).astype(
                np.float32
            )
            / 255.0
        )
        x = ((x - mean) / std).transpose(2, 0, 1)[None]
        dets, labels, masks = session.run(["dets", "labels", "masks"], {inp.name: x})
        scores = 1 / (1 + np.exp(-labels[0].max(axis=-1)))
        keep = scores > 0.25
        # Las máscaras elegidas se llevan al tamaño de la foto, como haría el servicio.
        for m in masks[0][keep]:
            cv2.resize(
                m.astype(np.float32),
                (img.shape[1], img.shape[0]),
                interpolation=cv2.INTER_LINEAR,
            )
        return int(keep.sum())

    return predict


def run(
    model: str,
    backend: str,
    images: list[np.ndarray],
    warmup: int,
    runs: int,
    imgsz: int | None,
    threads: int | None = None,
) -> dict:
    proc = psutil.Process()
    rss_before = proc.memory_info().rss
    import torch

    if torch.cuda.is_available():
        raise SystemExit("La GPU sigue visible: la medición en CPU no sería válida")
    t0 = time.perf_counter()
    predict, info, weights = build_predictor(model, backend, imgsz, threads)
    load_s = time.perf_counter() - t0
    if (
        threads
    ):  # después de cargar: Ultralytics cambia el número de hilos al importarse
        import torch

        torch.set_num_threads(threads)
    for i in range(warmup):
        predict(images[i % len(images)])
    times, detections, peak_rss = [], [], proc.memory_info().rss
    torch_threads_seen = 0
    for i in range(runs):
        img = images[i % len(images)]
        start = time.perf_counter()
        detections.append(predict(img))
        times.append(time.perf_counter() - start)
        peak_rss = max(peak_rss, proc.memory_info().rss)
        torch_threads_seen = max(torch_threads_seen, torch.get_num_threads())
    times.sort()
    import torch

    return {
        "model": model,
        "backend": backend,
        **info,
        "weights_file": weights.name,
        "runs": runs,
        "warmup": warmup,
        "load_seconds": round(load_s, 2),
        "p50_s": round(statistics.median(times), 3),
        "p95_s": round(times[min(len(times) - 1, int(0.95 * len(times)))], 3),
        "max_s": round(times[-1], 3),
        "mean_detections": round(statistics.mean(detections), 1),
        "rss_peak_mb": round(peak_rss / 2**20),
        "rss_model_mb": round((peak_rss - rss_before) / 2**20),
        "threads_limit": threads,
        "cpu_affinity": proc.cpu_affinity(),
        "torch_threads": torch.get_num_threads(),
        "torch_threads_max_seen": torch_threads_seen,
        "peak_working_set_mb": round(getattr(proc.memory_info(), "peak_wset", 0) / 2**20),
        "cuda_visible": torch.cuda.is_available(),
    }


def _power_state() -> dict:
    """Batería y plan de energía: con batería o en ahorro la CPU baja su frecuencia."""
    battery = psutil.sensors_battery()
    state = {"on_ac_power": None if battery is None else bool(battery.power_plugged),
             "battery_percent": None if battery is None else battery.percent}
    try:
        import subprocess

        state["power_plan"] = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True,
                                             timeout=10).stdout.strip().split("(")[-1].rstrip(")")
    except OSError:
        state["power_plan"] = None
    return state


def machine() -> dict:
    import subprocess

    cpu = platform.processor()
    try:
        cpu = (
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).Name",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
            or cpu
        )
    except OSError:
        pass
    return {
        "cpu": cpu,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "power": _power_state(),
        "os": platform.platform(),
        "python": platform.python_version(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        required=True,
        choices=["yolo11s-seg", "rfdetr-seg-nano", "rfdetr-seg-small"],
    )
    parser.add_argument("--backend", default="torch", choices=["torch", "onnx"])
    parser.add_argument("--images", type=Path, default=None)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Limita los hilos para simular un equipo con menos núcleos",
    )
    parser.add_argument("--out", type=Path, default=Path("results/latencia"))
    args = parser.parse_args()
    if args.threads:
        import torch

        torch.set_num_threads(args.threads)
    images = load_images(args.images, min(args.runs, 20))
    result = run(
        args.model,
        args.backend,
        images,
        args.warmup,
        args.runs,
        args.imgsz,
        args.threads,
    )
    result["images"] = (
        "sintéticas 2048x1536"
        if args.images is None
        else f"{len(images)} fotos reales reducidas a {LONG_SIDE} px"
    )
    result["machine"] = machine()
    result["threshold_p95_s"] = 10.0
    result["meets_threshold"] = result["p95_s"] <= 10.0
    args.out.mkdir(parents=True, exist_ok=True)
    tag = "real" if args.images else "sintetica"
    suffix = f"-{args.threads}hilos" if args.threads else ""
    (args.out / f"{args.model}-{args.backend}-{tag}{suffix}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "model",
                    "backend",
                    "p50_s",
                    "p95_s",
                    "rss_peak_mb",
                    "meets_threshold",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
