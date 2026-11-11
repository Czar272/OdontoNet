"""mAP50 de máscara por pieza FDI en validación, para un modelo YOLO entrenado (ODON-266).

Mide sobre el conjunto de VALIDACIÓN, nunca sobre el de prueba (que se reserva para ODON-267).

Uso (desde ai-service/):
    .venv/Scripts/python -m research.val_per_class --weights runs/smoke-yolo11s-seg/weights/best.pt \
        --data ../../Datasets_Odontonet/IOP-Compass-yolo/data.yaml --out results/entrenamiento-iop/yolo11s-seg-por-pieza-val.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research.iop_dataset import THIRD_MOLARS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from ultralytics import YOLO

    result = YOLO(str(args.weights)).val(
        data=str(args.data), split="val", imgsz=args.imgsz, batch=8, device=0, plots=False, verbose=False
    )
    per_fdi = {
        result.names[int(c)]: round(float(ap), 3) for c, ap in zip(result.seg.ap_class_index, result.seg.ap50)
    }
    third = {str(f): per_fdi.get(str(f)) for f in THIRD_MOLARS}
    others = [v for k, v in per_fdi.items() if int(k) not in THIRD_MOLARS]
    summary = {
        "split": "val",
        "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
        "mask_ap50_by_fdi": per_fdi,
        "third_molars": third,
        "others_mean": round(sum(others) / len(others), 3),
        "others_min": min(others),
        "note": "Validación de un modelo de prueba corta; no es un resultado final ni mide ausencia clínica.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("third_molars", "others_mean", "others_min")}))


if __name__ == "__main__":
    main()
