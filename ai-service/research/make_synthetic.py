"""Dataset sintético con formato YOLO-seg y 32 clases (ODON-266).

Sirve para probar el entrenamiento y medir VRAM sin datos reales: la memoria
depende del tamaño de imagen, del lote y del número de instancias, no del
contenido. Dibuja figuras de color sobre un fondo; no se parece a una boca.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.make_synthetic --out ../../Datasets_Odontonet/_sintetico --train 160 --val 32
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from research.iop_dataset import FDI_PERMANENT


def make_image(rng: np.random.Generator, width: int, height: int, n: int) -> tuple[np.ndarray, list[str]]:
    img = np.full((height, width, 3), rng.integers(60, 120), dtype=np.uint8)
    lines = []
    classes = rng.choice(len(FDI_PERMANENT), size=n, replace=False)
    for cls in classes:
        cx, cy = rng.uniform(0.08, 0.92) * width, rng.uniform(0.1, 0.9) * height
        rx, ry = rng.uniform(0.02, 0.05) * width, rng.uniform(0.05, 0.12) * height
        angles = np.sort(rng.uniform(0, 2 * np.pi, 24))
        pts = np.stack([cx + rx * np.cos(angles), cy + ry * np.sin(angles)], axis=1)
        color = tuple(int(c) for c in rng.integers(150, 255, 3))
        cv2.fillPoly(img, [pts.astype(np.int32)], color)
        norm = np.clip(pts / [width, height], 0, 1).ravel()
        lines.append(f"{cls} " + " ".join(f"{v:.6f}" for v in norm))
    return img, lines


def build(out: Path, n_train: int, n_val: int, width: int, height: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    for subset, count in (("train", n_train), ("val", n_val)):
        (out / "images" / subset).mkdir(parents=True, exist_ok=True)
        (out / "labels" / subset).mkdir(parents=True, exist_ok=True)
        for i in range(count):
            img, lines = make_image(rng, width, height, int(rng.integers(14, 29)))
            cv2.imwrite(str(out / "images" / subset / f"s{i:04d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            (out / "labels" / subset / f"s{i:04d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    names = "\n".join(f"  {i}: '{fdi}'" for i, fdi in enumerate(FDI_PERMANENT))
    (out / "data.yaml").write_text(f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\nnames:\n{names}\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--train", type=int, default=160)
    parser.add_argument("--val", type=int, default=32)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=960)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    build(args.out, args.train, args.val, args.width, args.height, args.seed)
    print(f"Dataset sintético en {args.out}")


if __name__ == "__main__":
    main()
