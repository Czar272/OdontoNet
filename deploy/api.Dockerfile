# API de OdontoNet para producción (ODON-238). Contexto de build: raíz del repositorio.
FROM python:3.11.17-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Lista explícita: ni pruebas, ni seeds, ni archivos locales.
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts/bootstrap_clinic.py backend/scripts/verify_images.py backend/scripts/verify_audit.py backend/scripts/verify_fresh_install.py ./scripts/

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin odontonet \
    && mkdir -p /data/images \
    && chown -R odontonet /data
USER odontonet

EXPOSE 8000

# Sin registro de accesos: las URL llevan búsquedas con nombres de pacientes (?q=).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-server-header"]
