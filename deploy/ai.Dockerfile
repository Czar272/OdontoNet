# Servicio de inferencia de OdontoNet (ODON-269). Contexto de build: raíz del repositorio.
# Corre en CPU y sin internet. Los pesos y sus metadatos NO van en la imagen: se montan de solo
# lectura en /model (AI_MODEL_PATH, AI_MODEL_META). Licencia de Ultralytics: AGPL-3.0, línea de tesis.
FROM python:3.12.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    YOLO_OFFLINE=1 \
    OPENCV_IO_MAX_IMAGE_PIXELS=16777216 \
    AI_MODEL_PATH=/model/best.pt \
    AI_MODEL_META=/model/meta.json

# libGL y glib, que necesita OpenCV dentro de Ultralytics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PyTorch solo para CPU: la imagen no lleva CUDA.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.14.1+cpu torchvision==0.29.1+cpu
COPY ai-service/requirements-service.txt ./
RUN pip install --no-cache-dir -r requirements-service.txt

# Lista explícita: solo el servicio, ni investigación, ni pruebas, ni pesos.
COPY ai-service/service ./service

RUN useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin odontonet-ai
USER odontonet-ai

EXPOSE 8001

CMD ["uvicorn", "service.main:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8001", "--no-access-log", "--no-server-header"]
