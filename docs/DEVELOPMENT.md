# Guía de desarrollo de OdontoNet

## Requisitos

- Windows y PowerShell (comandos documentados); Linux/macOS requieren adaptar la activación del entorno virtual.
- Python 3.11 disponible mediante `py -3.11`.
- Node.js/npm compatibles con Vite 8 y las versiones indicadas en `frontend/package.json`; comprobar requisitos de Node antes de instalar.
- Docker Desktop con Docker Compose.
- Git.

## 1. Clonar y configurar variables

Desde la raíz del repositorio:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

En `.env` de la raíz configura `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `POSTGRES_PORT`. En `backend/.env` configura `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM=HS256` y `ACCESS_TOKEN_EXPIRE_MINUTES`.

La contraseña, usuario, base y puerto de `DATABASE_URL` deben coincidir con los de Docker. Si una contraseña contiene caracteres reservados de URL (`@`, `:`, `/`, `#`, etc.), codifícala en la URL.

Para generar una clave JWT local:

```powershell
py -3.11 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Nunca publicar `.env`, claves JWT ni volcados de pacientes. Los archivos `.env.example` contienen marcadores, no credenciales reales.

## 2. Base de datos

```powershell
docker compose config --quiet
docker compose up -d
docker compose ps
```

Espera a que `odontonet-db` aparezca como `healthy`. El puerto de PostgreSQL se publica únicamente en `127.0.0.1`.

**No ejecutar `docker compose down -v` salvo que se quiera borrar deliberadamente el volumen de datos.**

## 3. Backend

En una nueva terminal, desde la raíz:

```powershell
cd backend
py -3.11 -m venv odonto_venv
.\odonto_venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
alembic upgrade head
alembic current
alembic heads
uvicorn app.main:app --reload
```

Si `odonto_venv` ya existe, omite su creación. `alembic current` y `alembic heads` deben apuntar a la misma revisión.

- API: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs

El endpoint `/auth/me` **requiere** JWT. Para probarlo, usa `POST /auth/login`, copia `access_token`, presiona `Authorize` en Swagger y ejecuta `GET /auth/me`. Un `403 Not authenticated` al abrirlo directamente en el navegador es esperado en la configuración actual.

## 4. Frontend

En otra terminal desde la raíz:

```powershell
cd frontend
npm ci
npm run dev
```

Abrir http://localhost:5173. Para comprobar compilación y lint:

```powershell
npm run build
npm run lint
```

Los comandos son verificaciones recomendadas; **no se garantiza que todos pasen sin correcciones**, ya que no se ha ejecutado la batería completa en un entorno limpio.

## 5. Datos iniciales

Alembic crea las tablas, pero no crea usuarios ni clínicas de manera automática. El repositorio no incluye `seed.py`, por decisión del proyecto: los datos sintéticos se mantienen locales. El aprovisionamiento seguro de la primera clínica y el administrador está pendiente. Para pruebas de login se necesita una base de desarrollo con usuarios válidos previamente creados.

La futura importación de datos de clínicas existentes será una funcionalidad específica, con validación de estructura, duplicados, permisos y trazabilidad; **no** equivale al seed de desarrollo.

## 6. Migraciones

Desde `backend/` con el entorno activo:

```powershell
alembic current
alembic heads
alembic revision --autogenerate -m "descripcion del cambio"
```

Revisar manualmente el archivo generado antes de aplicar:

```powershell
alembic upgrade head
```

Nunca asumir que `--autogenerate` detecta correctamente renombrados o migraciones de datos. Evitar resets de volumen como alternativa a migraciones.

## 7. Comprobaciones rápidas

- `docker compose ps`: contenedor saludable.
- `alembic current`: revisión actual coincide con `heads`.
- `GET /`: `200` y mensaje de API activa.
- `GET /docs` y `GET /openapi.json`: `200`.
- `POST /auth/login`: devuelve JWT para usuario existente.
- `GET /auth/me`: `200` con token válido; rechazo sin token.
- `npm run dev`: interfaz disponible.
- `git status --short`: comprobar cambios esperados antes de cada commit.

## 8. Problemas frecuentes

| Síntoma                               | Causa probable / acción                                                      |
| ------------------------------------- | ---------------------------------------------------------------------------- |
| `POSTGRES_USER requerido`             | Falta `.env` de la raíz o variable sin valor.                                |
| `connection refused` puerto 5432      | Docker detenido, contenedor no saludable o puerto incorrecto.                |
| `ModuleNotFoundError: app`            | Ejecutar Uvicorn/Alembic desde `backend/`.                                   |
| `403 Not authenticated` en `/auth/me` | Falta encabezado `Authorization: Bearer <JWT>`.                              |
| `alembic current` distinto de `heads` | Migraciones pendientes; revisar antes de aplicar.                            |
| `IntegrityError` con `clinic_id`      | Endpoint no asigna clínica; limitación actual conocida, no desactivar la FK. |
| CORS bloqueado                        | Verificar origen `http://localhost:5173` y configuración de `main.py`.       |

## 9. Seguridad operativa

No desplegar públicamente el backend actual. Antes de usar datos reales deben completarse aislamiento por clínica, autorización, validación de entradas, auditoría y políticas de privacidad/retención. No compartir capturas de tokens ni archivos `.env`.
