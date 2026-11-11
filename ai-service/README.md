# OdontoNet — AI Service

Este directorio está reservado para el futuro microservicio de inteligencia artificial de OdontoNet.

## Objetivo

Desarrollar un servicio independiente para procesar imágenes odontológicas y asistir en la generación de periodontogramas.

## Estado

**No implementado.** El contrato v1 está definido en [`docs/AI_INTEGRATION.md`](../docs/AI_INTEGRATION.md) (ODON-250); la implementación es ODON-269.

El desarrollo del modelo de IA se realizará independientemente del sistema clínico.

## Integración prevista

El backend de OdontoNet llama a este servicio por HTTP en la red interna (`GET /health`, `GET /v1/model`, `POST /v1/analyses/tooth-status`). El servicio corre en CPU, sin internet, no recibe identificadores de paciente ni de clínica y no guarda imágenes. La primera versión sugiere presencia o ausencia de cada pieza FDI.

Las mediciones generadas por inteligencia artificial deberán ser revisadas y validadas por un profesional odontológico antes de incorporarse al expediente clínico.

## Investigación (ODON-266)

Herramientas para preparar el modelo, separadas del servicio que se implementará en ODON-269. Resultados y decisión en [`docs/viabilidad.md`](docs/viabilidad.md).

```powershell
# En ai-service/, con Python 3.12
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-research.txt
.venv\Scripts\python -m pytest                       # pruebas del lector y la partición (datos sintéticos)
.venv\Scripts\python -m research.audit_iop --root ..\..\Datasets_Odontonet\IOP-Compass\IOP-Compass --out results\auditoria-iop.json
.venv\Scripts\python -m research.convert_yolo --root ..\..\Datasets_Odontonet\IOP-Compass\IOP-Compass --out ..\..\Datasets_Odontonet\IOP-Compass-yolo
bash research/run_latency.sh ..\..\Datasets_Odontonet\_latencia-real   # latencia en CPU (todos, 4 y 2 núcleos)
$env:PYTHONUTF8 = "1"; .venv\Scripts\python -m research.train_smoke --model yolo11s-seg --data ..\..\Datasets_Odontonet\IOP-Compass-yolo\data.yaml --epochs 3
```

- Los datasets viven fuera del repositorio, en `Datasets_Odontonet/` junto a `OdontoNet/`. Pesos (`weights/`), entrenamientos (`runs/`), modelos `.onnx` y logs no se versionan.
- Las versiones de `requirements-research.txt` tienen al menos 14 días de publicadas. Ultralytics (YOLO) es AGPL-3.0 y solo se usa en la línea de tesis.
- Ningún entrenamiento usa volteo horizontal: el espejo cambia el cuadrante y haría falsa la etiqueta FDI.

## Consideraciones

- Mantener dependencias independientes del backend clínico.
- No incluir imágenes de pacientes ni datasets privados en Git.
- Versionar los contratos de comunicación entre servicios.
- Documentar modelos, métricas y limitaciones antes de su integración.
