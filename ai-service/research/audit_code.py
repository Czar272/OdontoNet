"""Auditoría del dataset COde (zirak-ai, doi:10.57967/hf/6421) sin extraer el zip.

Solo produce conteos y distribuciones; no copia imágenes ni texto clínico.

Uso (desde ai-service/):
    .venv/Scripts/python -m research.audit_code --zip ../../Datasets_Odontonet/COde-dataset/COde-Dataset.zip --out results/auditoria-code.json
"""

from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import random
import re
import statistics
import zipfile
from pathlib import Path

from PIL import Image

TERMS = {
    "pieza_ausente": r"\bmissing\b|edentulous",
    "sondaje": r"\bprob(e|ing)\b",
    "bolsa": r"\bpocket",
    "sangrado": r"bleeding",
    "recesion": r"recession",
    "movilidad": r"mobility",
    "furcacion": r"furcation",
    "placa": r"plaque",
    "calculo": r"calculus",
    "implante": r"implant",
    "periodontitis": r"periodontitis",
    "gingivitis": r"gingivitis",
}


def _stats(values: list[float]) -> dict:
    if not values:
        return {}
    values = sorted(values)
    return {"min": values[0], "p50": values[len(values) // 2], "max": values[-1], "mean": round(statistics.mean(values), 1)}


def audit(zip_path: Path, sample: int) -> dict:
    z = zipfile.ZipFile(zip_path)
    names = z.namelist()
    photos = [n for n in names if n.startswith("Images/Photographs/") and n.lower().endswith(".jpg")]
    xrays = [n for n in names if n.startswith("Images/Radiographs/") and n.lower().endswith(".jpg")]
    rng = random.Random(0)
    res, exif_tags, gps = collections.Counter(), collections.Counter(), 0
    for n in rng.sample(photos, min(sample, len(photos))):
        img = Image.open(io.BytesIO(z.read(n)))
        res[f"{img.size[0]}x{img.size[1]}"] += 1
        exif = img.getexif()
        for tag in exif:
            exif_tags[tag] += 1
        if 34853 in exif:  # GPSInfo
            gps += 1
    xres = collections.Counter()
    for n in rng.sample(xrays, min(sample // 3, len(xrays))):
        xres[f"{Image.open(io.BytesIO(z.read(n))).size}"] += 1

    rows = list(csv.DictReader(io.StringIO(z.read("complete_dataset.csv").decode("utf-8-sig"))))
    ages = [float(r["age"]) for r in rows if re.fullmatch(r"\d+(\.\d+)?", r["age"].strip())]
    years = collections.Counter(m.group(0) for r in rows if (m := re.search(r"(19|20)\d\d", r["checkup_time"])))
    photos_per = [len([p for p in r["photographs"].split(",") if p.strip()]) for r in rows]
    xrays_per = [len([p for p in r["radiographs"].split(",") if p.strip()]) for r in rows]
    per_patient = collections.Counter(r["patient_id"] for r in rows)
    anomalies = collections.Counter(a.strip().lower() for r in rows for a in r["anomalies_en"].split(",") if a.strip())
    text = {k: 0 for k in TERMS}
    for r in rows:
        blob = " ".join([r["examination"], r["diagnosis"], r["radiographs_examination"]])
        for k, pattern in TERMS.items():
            if re.search(pattern, blob, re.I):
                text[k] += 1
    mm_probing = sum(1 for r in rows if re.search(r"(probing depth|pocket|PD)[^.]{0,40}\d+\s*mm", r["examination"], re.I))
    split_patients = collections.defaultdict(set)
    for r in rows:
        split_patients[r["split"]].add(r["patient_id"])
    leak = len(split_patients["train"] & split_patients["test"])
    jsons = {}
    for n in names:
        if n.endswith(".json"):
            data = json.loads(z.read(n))
            first = data[0] if isinstance(data, list) and data else data
            jsons[n] = {"entries": len(data) if isinstance(data, list) else None,
                        "keys": sorted(first.keys())[:12] if isinstance(first, dict) else str(type(first).__name__)}
    return {
        "zip": zip_path.name,
        "files": {"photographs": len(photos), "radiographs": len(xrays), "other": [n for n in names if not n.lower().endswith(".jpg") and not n.endswith("/")]},
        "photo_resolution_sample": dict(res.most_common(8)),
        "photo_exif_tags_in_sample": {str(k): v for k, v in exif_tags.most_common(10)},
        "photos_with_gps_in_sample": gps,
        "radiograph_resolution_sample": dict(xres.most_common(5)),
        "checkups": len(rows),
        "patients": len(per_patient),
        "checkups_per_patient": _stats(list(per_patient.values())),
        "age": _stats(ages),
        "gender": dict(collections.Counter(r["gender"] for r in rows)),
        "checkup_years": dict(sorted(years.items())),
        "photos_per_checkup": _stats(photos_per),
        "radiographs_per_checkup": _stats(xrays_per),
        "split_checkups": dict(collections.Counter(r["split"] for r in rows)),
        "patients_in_train_and_test": leak,
        "top_anomalies": dict(anomalies.most_common(25)),
        "distinct_anomalies": len(anomalies),
        "checkups_mentioning": text,
        "checkups_with_probing_or_pocket_in_mm": mm_probing,
        "json_files": jsons,
        "columns": list(rows[0].keys()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sample", type=int, default=600)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.zip, args.sample)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
