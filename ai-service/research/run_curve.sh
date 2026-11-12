#!/usr/bin/env bash
# Curva de aprendizaje de ODON-267, reanudable: salta las corridas que ya tienen registro.
# Uso (desde ai-service/, conectado a la corriente):  bash research/run_curve.sh
#
# Diseño reducido (decisión del desarrollador del 2026-11-12, antes de ver resultados de la curva,
# para cerrar el proyecto en el día): 25, 50 y 100 % de los pacientes de entrenamiento x semillas 0 y 1,
# todas con el mismo presupuesto de 30 épocas (el modelo principal ya estaba en meseta hacia la época 25).
# Cada corrida congela su umbral en su propia validación y se evalúa UNA vez en prueba.
# El modelo del criterio de aceptación sigue siendo yolo11s-seg-f100-s0 (89 épocas).
set -u -o pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
EPOCHS=30
mkdir -p runs results/entrenamiento results/evaluacion

run() {  # fracción semilla
  local name="yolo11s-seg-f$(.venv/Scripts/python -c "print(int($1*100))")-s$2-e$EPOCHS"
  .venv/Scripts/python -c "import psutil,sys; b=psutil.sensors_battery(); sys.exit(0 if b is None or b.power_plugged else 1)" \
    || { echo "Sin corriente: me detengo antes de $name"; exit 2; }
  if [ ! -f "results/entrenamiento/$name.json" ]; then
    echo "entrenando: $name ($(date +%H:%M))"
    .venv/Scripts/python -m research.train --model yolo11s-seg --fraction "$1" --seed "$2" --epochs $EPOCHS \
      > "runs/train-$name.log" 2>&1 || { echo "falló el entrenamiento: $name"; exit 1; }
  fi
  local weights="runs/$name/weights/best.pt"
  if [ ! -f "results/evaluacion/$name-umbral.json" ]; then
    .venv/Scripts/python -m research.evaluate --model yolo11s-seg --weights "$weights" --split val --name "$name" \
      > "runs/eval-$name-val.log" 2>&1 || { echo "falló la validación: $name"; exit 1; }
  fi
  if [ ! -f "results/evaluacion/$name-test.json" ]; then
    .venv/Scripts/python -m research.evaluate --model yolo11s-seg --weights "$weights" --split test --name "$name" \
      --frozen "results/evaluacion/$name-umbral.json" > "runs/eval-$name-test.log" 2>&1 \
      || { echo "falló la prueba: $name"; exit 1; }
  fi
  echo "listo: $name ($(date +%H:%M))"
}

for seed in 0 1; do
  for f in 0.25 0.5 1.0; do run "$f" "$seed"; done
done
echo "curva completa"
