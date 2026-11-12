# OdontoNet — AI Service

Microservicio de inteligencia artificial de OdontoNet, separado del backend clínico, e investigación del modelo.

## Objetivo

Desarrollar un servicio independiente para procesar imágenes odontológicas y asistir en la generación de periodontogramas.

## Estado

- **Servicio de inferencia (ODON-269):** implementado y probado en `service/`, según el contrato v1 de [`docs/AI_INTEGRATION.md`](../docs/AI_INTEGRATION.md) (ODON-250).
- **Modelo (ODON-267):** YOLO11s-seg entrenado con IOP-Compass, que cumple el criterio fijado antes de evaluar. Ver [`docs/ficha-modelo.md`](docs/ficha-modelo.md).
- **Integración con el backend y la interfaz de revisión (ODON-270 y 271):** diseñadas en el contrato, sin implementar.

## Servicio de inferencia (ODON-269)

| Ruta | Token | Qué hace |
| --- | --- | --- |
| `GET /health` | No | `200 {"status": "ok"}` con el modelo cargado; si no, `503` |
| `GET /v1/model` | Sí | Nombre, versión, SHA-256 de los pesos, etiquetas y límites |
| `POST /v1/analyses/tooth-status` | Sí | De 1 a 5 fotos con su vista. Devuelve las detecciones por foto y el estado de las 32 piezas: `present`, `absent` («no visible donde la zona sí se ve») o `uncertain` |

**Reglas del servicio:**
- El token (`X-Service-Token`, de 32 caracteres o más) se compara en tiempo constante.
- Solo acepta `request_id` (UUID), `images` y `views`: cualquier otro campo, como un identificador de paciente, se rechaza con `400`.
- Procesa en memoria, no escribe archivos y sus logs solo llevan el `request_id` y el tiempo.
- Cada foto pasa un control de calidad: tamaño mínimo, nitidez, brillo y presencia de dientes. Una foto que no pasa se excluye y no se le corre el modelo.
- **Una pieza no detectada nunca es `absent` si ninguna foto usable de una vista que normalmente la muestra la cubre**, ni si su confianza queda cerca del umbral. Los terceros molares siempre son `uncertain`.
- La cobertura por vista, el umbral (congelado en validación en ODON-267) y las piezas que nunca son `absent` vienen en `meta.json`, que genera `research/export_model.py`. Si el SHA-256 de los pesos no coincide con el de `meta.json`, el servicio no arranca.

**Imagen Docker** (`deploy/ai.Dockerfile`):
- PyTorch solo para CPU, usuario sin privilegios y sin pesos dentro.
- El modelo se monta de solo lectura en `/model`.
- Se puede probar en local así:

```powershell
docker build -f deploy/ai.Dockerfile -t odontonet-ai:dev .
docker run --rm -p 127.0.0.1:18001:8001 -e AI_SERVICE_TOKEN=<32+ caracteres> -v <carpeta con best.pt y meta.json>:/model:ro --read-only --tmpfs /tmp odontonet-ai:dev
```

**Límites:**
- Se revisan **antes** de decodificar: tamaño declarado del cuerpo, 5 archivos, 10 MB por foto, solo JPEG y 4096 px de lado, leídos de la cabecera.
- El formulario multipart se mantiene en memoria (no se vuelca a un temporal en disco) y se cierra al terminar.
- Ante un error inesperado, el log guarda el tipo de error y su traza, nunca el contenido de la petición.

**Latencia (`research/bench_service.py`, 2026-11-12):** análisis de 5 fotos a 2048 px en CPU, p95 0,95 s con todos los núcleos y 1,52 s limitado a 2, frente a 120 s del contrato. Resultados en `results/latencia-servicio/`.

**Despliegue:** la integración en `compose.prod.yml` (red interna, sin puertos publicados, `read_only` y `tmpfs /tmp`) queda para ODON-270, junto con el backend que lo llama.

Ultralytics es AGPL-3.0 y los datos de entrenamiento son CC BY-NC-SA: la imagen con estos pesos es solo para la línea de tesis, sin distribuirse a clínicas (ODON-275).

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
