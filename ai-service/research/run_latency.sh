#!/usr/bin/env bash
# Mediciones de latencia en CPU (ODON-266): 3 modelos x 2 motores x (todos los hilos, 4 y 2).
# Uso: bash research/run_latency.sh [carpeta_de_fotos]
set -u -o pipefail
cd "$(dirname "$0")/.."
IMAGES=${1:-}
for threads in ${THREADS:-0 4 2}; do
  for model in yolo11s-seg rfdetr-seg-nano rfdetr-seg-small; do
    for backend in torch onnx; do
      args=(--model "$model" --backend "$backend" --runs 50 --warmup 5)
      if [ -n "$IMAGES" ]; then args+=(--images "$IMAGES"); fi
      if [ "$threads" != 0 ]; then args+=(--threads "$threads"); fi
      .venv/Scripts/python -m research.bench_cpu "${args[@]}" 2>/dev/null | tail -1 \
        || echo "{\"model\":\"$model\",\"backend\":\"$backend\",\"threads\":$threads,\"error\":true}"
    done
  done
done
