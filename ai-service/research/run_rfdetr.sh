#!/usr/bin/env bash
# Anexo exploratorio de ODON-267: RF-DETR Seg Small al 100 %, 1 semilla, con presupuesto reducido de épocas.
# La comparación planeada pasó a trabajo futuro el 2026-11-12; esto se agrega después, como descriptivo.
# Mismo flujo que run_curve.sh: entrena, congela el umbral en validación y evalúa la prueba UNA vez.
# Reanudable: si ya existe un paso, lo salta. Se detiene sin corriente.
#   bash research/run_rfdetr.sh >> runs/rfdetr.log 2>&1
set -u
cd "$(dirname "$0")/.."
EPOCHS="${EPOCHS:-20}"
export HF_HUB_OFFLINE=1 YOLO_OFFLINE=1  # sin depender de la red: pesos en weights/
name="rfdetr-seg-small-f100-s0-e$EPOCHS"
weights="runs/$name/checkpoint_best_total.pth"

.venv/Scripts/python -c "import psutil,sys; b=psutil.sensors_battery(); sys.exit(0 if b is None or b.power_plugged else 1)" \
  || { echo "Sin corriente: me detengo antes de $name"; exit 2; }
if [ ! -f "results/entrenamiento/$name.json" ]; then
  echo "entrenando: $name ($(date +%H:%M))"
  PYTHONUTF8=1 .venv/Scripts/python -m research.train --model rfdetr-seg-small --fraction 1.0 --seed 0 --epochs "$EPOCHS" \
    > "runs/train-$name.log" 2>&1 || { echo "falló el entrenamiento: $name ($(date +%H:%M))"; exit 1; }
fi
if [ ! -f "results/evaluacion/$name-umbral.json" ]; then
  echo "validación: $name ($(date +%H:%M))"
  .venv/Scripts/python -m research.evaluate --model rfdetr-seg-small --weights "$weights" --split val --name "$name" \
    > "runs/eval-$name-val.log" 2>&1 || { echo "falló la validación: $name"; exit 1; }
fi
if [ ! -f "results/evaluacion/$name-test.json" ]; then
  echo "prueba: $name ($(date +%H:%M))"
  .venv/Scripts/python -m research.evaluate --model rfdetr-seg-small --weights "$weights" --split test --name "$name" \
    --frozen "results/evaluacion/$name-umbral.json" > "runs/eval-$name-test.log" 2>&1 \
    || { echo "falló la prueba: $name"; exit 1; }
fi
.venv/Scripts/python -m research.summarize > runs/resumen-rfdetr.log 2>&1
echo "listo: $name ($(date +%H:%M))"
