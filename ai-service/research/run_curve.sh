#!/usr/bin/env bash
# Corridas de ODON-267, reanudables: salta las que ya tienen su registro en results/entrenamiento/.
# Uso (desde ai-service/, conectado a la corriente):  bash research/run_curve.sh [yolo|rfdetr|all]
#
# Orden: primero YOLO11s-seg al 100 % con semilla 0 (el modelo del criterio de aceptación),
# luego la curva de YOLO (25/50/75/100 % x semillas 0-4) y al final RF-DETR Seg Small al 100 % (semillas 0-2).
set -u -o pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
WHAT=${1:-all}
mkdir -p runs results/entrenamiento

run() {  # modelo fracción semilla
  local name="$1-f$(.venv/Scripts/python -c "print(int($2*100))")-s$3"
  if [ -f "results/entrenamiento/$name.json" ]; then echo "ya existe: $name"; return 0; fi
  .venv/Scripts/python -c "import psutil,sys; b=psutil.sensors_battery(); sys.exit(0 if b is None or b.power_plugged else 1)" \
    || { echo "Sin corriente: me detengo antes de $name"; exit 2; }
  echo "entrenando: $name ($(date +%H:%M))"
  .venv/Scripts/python -m research.train --model "$1" --fraction "$2" --seed "$3" > "runs/train-$name.log" 2>&1 \
    || { echo "falló: $name (ver runs/train-$name.log)"; exit 1; }
}

if [ "$WHAT" = yolo ] || [ "$WHAT" = all ]; then
  run yolo11s-seg 1.0 0
  for seed in 0 1 2 3 4; do
    for f in 0.25 0.5 0.75 1.0; do run yolo11s-seg "$f" "$seed"; done
  done
fi
if [ "$WHAT" = rfdetr ] || [ "$WHAT" = all ]; then
  for seed in 0 1 2; do run rfdetr-seg-small 1.0 "$seed"; done
fi
echo "listo"
