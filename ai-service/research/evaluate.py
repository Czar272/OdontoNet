"""Evaluación común de ODON-267 para YOLO11s-seg y RF-DETR Seg (docs/AI_INTEGRATION.md §7.3).

Mide con el mismo código para ambos modelos:
- mAP de máscara (pycocotools, IoU 0,50 y 0,50:0,95) por vista;
- exactitud de numeración por vista: de las piezas anotadas que el modelo encuentra (IoU ≥ 0,5,
  sin mirar la clase), cuántas reciben el número FDI correcto;
- presencia por pieza y paciente («no visible»), con IC 95 % por bootstrap por paciente.

Flujo bloqueado:
1. `--split val`: elige el umbral de operación con la regla fijada (`choose_threshold`) y lo congela en
   results/evaluacion/<nombre>-umbral.json junto con el SHA-256 de los pesos.
2. `--split test --frozen <umbral.json>`: solo acepta los mismos pesos y aplica ese umbral. El conjunto
   de prueba se evalúa una vez; cualquier otra corrida se marca como exploratoria.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.evaluate --model yolo11s-seg --weights runs/yolo11s-seg-f100-s0/weights/best.pt --split val
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from research.experiment import (
    MAIN_TEETH,
    bootstrap_ci,
    choose_threshold,
    patient_counts,
    patient_scores,
    total,
)
from research.iop_dataset import FDI_PERMANENT, THIRD_MOLARS

AI_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA = AI_DIR.parent.parent / "Datasets_Odontonet" / "IOP-Compass-yolo"
SCORE_FLOOR = 0.05  # se guardan detecciones desde aquí para el umbral y el mAP
VIEWS = ("frontal", "right_lateral", "left_lateral", "upper_occlusal", "lower_occlusal")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_stem(stem: str) -> tuple[str, str]:
    """'687_upper_occlusal' -> ('687', 'upper_occlusal')."""
    pid, view = stem.split("_", 1)
    return pid, view


def read_labels(label_file: Path, width: int, height: int) -> list[tuple[int, list[float]]]:
    """(fdi, polígono en píxeles [x1, y1, x2, y2, ...]) desde una etiqueta YOLO-seg."""
    out = []
    if not label_file.exists():
        return out
    for line in label_file.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 7:
            continue
        cls, coords = int(parts[0]), [float(v) for v in parts[1:]]
        poly = [c * (width if i % 2 == 0 else height) for i, c in enumerate(coords)]
        out.append((FDI_PERMANENT[cls], poly))
    return out


def reference_visibility(gt_by_image: dict[str, list[tuple[int, list[float]]]]) -> dict[str, set[int]]:
    ref: dict[str, set[int]] = defaultdict(set)
    for stem, items in gt_by_image.items():
        pid, _ = parse_stem(stem)
        ref[pid].update(fdi for fdi, _ in items)
    return dict(ref)


class Predictor:
    """Envuelve YOLO o RF-DETR y devuelve [(fdi, confianza, máscara bool al tamaño de la imagen)]."""

    def __init__(self, model: str, weights: Path):
        self.kind = "yolo" if model.startswith("yolo") else "rfdetr"
        if self.kind == "yolo":
            from ultralytics import YOLO

            self.net = YOLO(str(weights))
        else:
            import rfdetr

            self.net = rfdetr.RFDETRSegSmall(pretrain_weights=str(weights))
            names = getattr(self.net, "class_names", None)
            # RF-DETR numera las clases según el dataset con que se entrenó; se mapea por nombre FDI.
            self.class_to_fdi = {i: int(n) for i, n in enumerate(names)} if names else None

    def __call__(self, image_bgr: np.ndarray) -> list[tuple[int, float, np.ndarray]]:
        if self.kind == "yolo":
            r = self.net.predict(image_bgr, conf=SCORE_FLOOR, retina_masks=True, device=0, verbose=False)[0]
            if r.masks is None:
                return []
            masks = r.masks.data.cpu().numpy() > 0.5
            return [(FDI_PERMANENT[int(c)], float(s), m) for c, s, m in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist(), masks)]
        det = self.net.predict(image_bgr[:, :, ::-1].copy(), threshold=SCORE_FLOOR)
        if det.mask is None:
            return []
        out = []
        for c, s, m in zip(det.class_id, det.confidence, det.mask):
            fdi = self.class_to_fdi.get(int(c)) if self.class_to_fdi else FDI_PERMANENT[int(c)]
            if fdi in FDI_PERMANENT:
                out.append((fdi, float(s), m.astype(bool)))
        return out


def mask_metrics(gt_by_image, preds_by_image, sizes, views_of) -> dict:
    """mAP de máscara por vista con pycocotools (mismo cálculo para ambos modelos)."""
    from pycocotools import mask as mask_utils
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    cats = [{"id": fdi, "name": str(fdi)} for fdi in FDI_PERMANENT]
    results = {}
    for view in (*VIEWS, "all"):
        stems = [s for s in gt_by_image if view == "all" or views_of[s] == view]
        if not stems:
            continue
        images, anns, dets = [], [], []
        for i, stem in enumerate(stems, start=1):
            w, h = sizes[stem]
            images.append({"id": i, "width": w, "height": h, "file_name": stem})
            for fdi, poly in gt_by_image[stem]:
                rle = mask_utils.merge(mask_utils.frPyObjects([poly], h, w))
                anns.append({"id": len(anns) + 1, "image_id": i, "category_id": fdi, "segmentation": [poly],
                             "area": float(mask_utils.area(rle)), "bbox": list(mask_utils.toBbox(rle)), "iscrowd": 0})
            for fdi, score, rle in preds_by_image.get(stem, []):
                dets.append({"image_id": i, "category_id": fdi, "segmentation": rle, "score": score})
        gt = COCO()
        gt.dataset = {"images": images, "annotations": anns, "categories": cats}
        gt.createIndex()
        if not dets:
            results[view] = {"mask_map50": 0.0, "mask_map50_95": 0.0, "images": len(stems)}
            continue
        ev = COCOeval(gt, gt.loadRes(dets), "segm")
        ev.params.maxDets = [1, 10, 100]
        ev.evaluate()
        ev.accumulate()
        ev.summarize()
        results[view] = {"mask_map50_95": round(float(ev.stats[0]), 4), "mask_map50": round(float(ev.stats[1]), 4), "images": len(stems)}
    return results


def numbering_accuracy(gt_by_image, preds_by_image, sizes, views_of, threshold: float) -> dict:
    """Por pieza anotada: ¿la mejor detección (IoU ≥ 0,5, sin mirar la clase) trae el FDI correcto?"""
    from pycocotools import mask as mask_utils

    acc = defaultdict(lambda: [0, 0, 0])  # vista -> [encontradas, bien numeradas, anotadas]
    for stem, items in gt_by_image.items():
        w, h = sizes[stem]
        preds = [(f, s, r) for f, s, r in preds_by_image.get(stem, []) if s >= threshold]
        pred_rles = [r for _, _, r in preds]
        for fdi, poly in items:
            gt_rle = mask_utils.merge(mask_utils.frPyObjects([poly], h, w))
            for key in (views_of[stem], "all"):
                acc[key][2] += 1
            if not pred_rles:
                continue
            ious = mask_utils.iou(pred_rles, [gt_rle], [0]).ravel()
            best = int(np.argmax(ious))
            if ious[best] >= 0.5:
                for key in (views_of[stem], "all"):
                    acc[key][0] += 1
                    acc[key][1] += preds[best][0] == fdi
    return {v: {"found": f, "correct_number": c, "annotated": n,
                "numbering_accuracy": round(c / f, 4) if f else None, "detection_rate": round(f / n, 4) if n else None}
            for v, (f, c, n) in acc.items()}


def presence_report(ref, scores, threshold, n_boot=2000) -> dict:
    out = {}
    for name, teeth in (("main_11_47_without_third_molars", MAIN_TEETH), ("third_molars", THIRD_MOLARS)):
        counts = patient_counts(ref, scores, threshold, teeth)
        t = total(counts)
        out[name] = {
            "tp": t.tp, "fn": t.fn, "tn": t.tn, "fp": t.fp,
            "sensitivity_not_visible": t.sensitivity, "specificity": t.specificity,
            "sensitivity_ci95": bootstrap_ci(counts, "sensitivity", n_boot),
            "specificity_ci95": bootstrap_ci(counts, "specificity", n_boot),
        }
    return out


def run(model: str, weights: Path, data_dir: Path, split: str, limit: int | None = None):
    import cv2
    from pycocotools import mask as mask_utils

    predictor = Predictor(model, weights)
    image_dir, label_dir = data_dir / "images" / split, data_dir / "labels" / split
    stems = sorted(p.stem for p in image_dir.glob("*.jpg"))[:limit]
    gt_by_image, preds_by_image, sizes, views_of, detections = {}, {}, {}, {}, []
    for stem in stems:
        image = cv2.imread(str(image_dir / f"{stem}.jpg"))
        h, w = image.shape[:2]
        pid, view = parse_stem(stem)
        sizes[stem], views_of[stem] = (w, h), view
        gt_by_image[stem] = read_labels(label_dir / f"{stem}.txt", w, h)
        preds = []
        for fdi, score, mask in predictor(image):
            rle = mask_utils.encode(np.asfortranarray(mask.astype(np.uint8)))
            rle["counts"] = rle["counts"].decode("ascii")
            preds.append((fdi, score, rle))
            detections.append((pid, fdi, score))
        preds_by_image[stem] = preds
    return gt_by_image, preds_by_image, sizes, views_of, detections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=["yolo11s-seg", "rfdetr-seg-small"])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--split", required=True, choices=["val", "test"])
    parser.add_argument("--frozen", type=Path, help="Umbral congelado en validación (obligatorio con --split test)")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--name", default=None)
    parser.add_argument("--limit", type=int, default=None, help="Solo para probar el script")
    parser.add_argument("--out", type=Path, default=AI_DIR / "results" / "evaluacion")
    args = parser.parse_args()

    weights_hash = sha256(args.weights)
    name = args.name or args.weights.parent.parent.name if args.model.startswith("yolo") else (args.name or args.weights.parent.name)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.split == "test":
        if not args.frozen:
            raise SystemExit("El conjunto de prueba exige --frozen con el umbral elegido en validación")
        frozen = json.loads(args.frozen.read_text(encoding="utf-8"))
        if frozen["weights_sha256"] != weights_hash:
            raise SystemExit("Los pesos no son los que se congelaron en validación")
        marker = args.out / f"{name}-test.json"
        exploratory = marker.exists()

    gt, preds, sizes, views_of, detections = run(args.model, args.weights, args.data, args.split, args.limit)
    ref = reference_visibility(gt)
    scores = patient_scores(detections)
    if args.split == "val":
        chosen = choose_threshold(ref, scores)
        threshold = chosen["threshold"]
        frozen_record = {"name": name, "model": args.model, "weights": args.weights.as_posix(), "weights_sha256": weights_hash,
                         "rule": "máxima sensibilidad con especificidad ≥ 0,95 en validación (piezas 11–47 sin terceros molares)",
                         **chosen, "limit": args.limit}
        (args.out / f"{name}-umbral.json").write_text(json.dumps(frozen_record, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        threshold = frozen["threshold"]

    report = {
        "name": name, "model": args.model, "split": args.split, "weights_sha256": weights_hash,
        "threshold": threshold, "patients": len(ref), "images": len(gt), "limit": args.limit,
        "presence": presence_report(ref, scores, threshold),
        "mask": mask_metrics(gt, preds, sizes, views_of),
        "numbering": numbering_accuracy(gt, preds, sizes, views_of, threshold),
    }
    if args.split == "test":
        main_ = report["presence"]["main_11_47_without_third_molars"]
        report["criterion"] = {
            "sensitivity_min": 0.80, "specificity_min": 0.95,
            "met": (main_["sensitivity_not_visible"] or 0) >= 0.80 and (main_["specificity"] or 0) >= 0.95,
            "exploratory": exploratory,
        }
    counts = patient_counts(ref, scores, threshold)
    report["per_patient_counts"] = {p: [c.tp, c.fn, c.tn, c.fp] for p, c in counts.items()}
    suffix = "-exploratoria" if args.split == "test" and exploratory else ""
    out_file = args.out / f"{name}-{args.split}{suffix}.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("name", "split", "threshold")} | {"presence": report["presence"]["main_11_47_without_third_molars"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
