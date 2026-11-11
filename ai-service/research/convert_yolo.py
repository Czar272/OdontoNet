"""Convierte IOP-Compass al formato YOLO-seg con división por paciente (ODON-266).

Escribe FUERA del repositorio:
    <salida>/images/{train,val,test}/<pid>_<vista>.jpg  (lado mayor reducido)
    <salida>/labels/{train,val,test}/<pid>_<vista>.txt
    <salida>/data.yaml
    <salida>/split.json  (ids de paciente por conjunto; se copia a results/)

Uso (desde ai-service/):
    .venv/Scripts/python -m research.convert_yolo --root <dataset> --out ../../IOP-Compass-yolo --long-side 1280

Las clases son las 32 piezas permanentes en orden FDI (11 → 0 … 48 → 31). Al
entrenar NO se debe voltear horizontalmente (fliplr=0): el espejo cambia el
cuadrante y haría falsa la etiqueta FDI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from research.iop_dataset import FDI_PERMANENT, discover, split_patients, yolo_segment_line


def convert(root: Path, out: Path, long_side: int, seed: int, n_val: int, n_test: int, limit: int | None) -> dict:
    records = [r for r in discover(root) if r.image is not None and r.annotation is not None]
    split = split_patients([r.patient_id for r in records], seed=seed, n_val=n_val, n_test=n_test)
    if limit:
        split = {k: v[: max(1, limit * len(v) // sum(len(x) for x in split.values()))] for k, v in split.items()}
    where = {pid: name for name, ids in split.items() for pid in ids}
    counts = {name: 0 for name in split}
    skipped = 0
    for r in records:
        subset = where.get(r.patient_id)
        if subset is None:
            continue
        image = cv2.imread(str(r.image), cv2.IMREAD_COLOR)
        if image is None:
            skipped += 1
            continue
        h, w = image.shape[:2]
        lines = [line for t in r.teeth if (line := yolo_segment_line(t, w, h))]
        scale = long_side / max(h, w)
        if scale < 1:
            image = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        stem = f"{r.patient_id}_{r.view}"
        (out / "images" / subset).mkdir(parents=True, exist_ok=True)
        (out / "labels" / subset).mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / "images" / subset / f"{stem}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        (out / "labels" / subset / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        counts[subset] += 1
    names = "\n".join(f"  {i}: '{fdi}'" for i, fdi in enumerate(FDI_PERMANENT))
    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n",
        encoding="utf-8",
    )
    meta = {"seed": seed, "long_side": long_side, "images": counts, "skipped_unreadable": skipped,
            "patients": {k: len(v) for k, v in split.items()}, "split": split}
    (out / "split.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--long-side", type=int, default=1280)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-val", type=int, default=200)
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--limit", type=int, default=None, help="Número aproximado de pacientes, para pruebas rápidas")
    args = parser.parse_args()
    meta = convert(args.root, args.out, args.long_side, args.seed, args.n_val, args.n_test, args.limit)
    print(json.dumps({k: meta[k] for k in ("images", "patients", "skipped_unreadable")}))


if __name__ == "__main__":
    main()
