# Guía de desarrollo de OdontoNet

## Requisitos

- Windows y PowerShell (comandos documentados); Linux/macOS requieren adaptar la activación del entorno virtual.
- Python 3.11 disponible mediante `py -3.11`.
- Node.js 22.22.2 o superior dentro de la línea 22 (o 24.15+), según `engines` de `frontend/package.json`; jsdom, usado por las pruebas, no admite versiones anteriores. Verificar con `node -v`.
- Docker Desktop con Docker Compose.
- Git.

## 1. Clonar y configurar variables

Desde la raíz del repositorio:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

En `.env` de la raíz configura `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `POSTGRES_PORT`. En `backend/.env` configura `DATABASE_URL`, `SECRET_KEY` (al menos 32 bytes), `ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES` y, opcionalmente, `SESSION_EXPIRE_HOURS` (12) y `REMEMBER_ME_EXPIRE_DAYS` (7).

Recuperación de contraseña (ODON-54): `FRONTEND_URL` (para armar el enlace), `PASSWORD_RESET_EXPIRE_MINUTES` y `PASSWORD_RESET_MAX_PER_HOUR` tienen valores por defecto. Con `SMTP_HOST` vacío no se envía nada: el correo, con el enlace, aparece en la consola de uvicorn (logger `odontonet.email`). Para probar con un servidor real, completa las variables `SMTP_*` de `backend/.env.example`.

Límite de intentos (ODON-230): `LOGIN_MAX_FAILURES_PER_ACCOUNT` (7), `LOGIN_MAX_FAILURES_PER_IP` (30), `LOGIN_WINDOW_MINUTES` y `LOGIN_LOCK_MINUTES` (15), `PASSWORD_RESET_MAX_PER_IP` (10) y `PASSWORD_RESET_CONFIRM_MAX_FAILURES_PER_IP` (30) tienen valores por defecto. `TRUST_PROXY_HEADERS=true` solo detrás de un proxy de confianza. Si te bloqueas en desarrollo, espera 15 minutos o vacía la tabla: `docker exec odontonet-db psql -U odontonet -d odontonet -c "DELETE FROM auth_attempts"`.

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

### Ver la base de datos con un cliente gráfico

No hace falta instalar PostgreSQL: ya corre en Docker. Solo se necesita un cliente que se conecte a él.

| Campo | Valor |
| --- | --- |
| Host | `localhost` (o `127.0.0.1`) |
| Puerto | `POSTGRES_PORT` del `.env` de la raíz (5432 por defecto) |
| Usuario / contraseña | `POSTGRES_USER` / `POSTGRES_PASSWORD` del `.env` de la raíz |
| Bases | `POSTGRES_DB` (desarrollo) y `<POSTGRES_DB>_test` (pruebas; se vacía en cada ejecución de pytest) |

- **DBeaver Community** (recomendado para diagramas): Nueva conexión → PostgreSQL → datos de la tabla; en *PostgreSQL → Show all databases* para ver ambas bases. El diagrama entidad-relación está en *esquema `public` → View Diagram*, con claves primarias, foráneas y restricciones únicas.
- **VS Code:** extensión *PostgreSQL* de Microsoft (`ms-ossdata.vscode-pgsql`), con los mismos datos de conexión, para consultar tablas sin salir del editor.
- La tabla `alembic_version` guarda la migración aplicada; no se edita a mano.
- Para cambiar datos usa la aplicación, el seed o una migración; modificar tablas desde el cliente puede dejar la base distinta de las migraciones.

### Rotar la contraseña de PostgreSQL de desarrollo

`POSTGRES_PASSWORD` solo se aplica al crear el volumen por primera vez; cambiarlo en `.env` no modifica una base existente. Para rotarla sin perder datos, con el contenedor en ejecución:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\rotate-db-password.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File scripts\dev\rotate-db-password.ps1
```

El script ejecuta `ALTER USER` dentro del contenedor, verifica la conexión y actualiza `.env` y `backend/.env` (con respaldo `*.bak-<fecha>`, ignorado por Git). Después, reinicia el backend y comprueba con `alembic current`.

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
- Estado de API y base de datos: http://127.0.0.1:8000/health

Los endpoints `/auth/me`, `/patients/`, `/doctors/` y `/users/` **requieren** JWT y devuelven solo datos de la clínica del usuario autenticado. Para probarlo, usa `POST /auth/login`, copia `access_token`, presiona `Authorize` en Swagger y ejecuta `GET /auth/me`. Sin token, la API responde `401 {"detail": "No autenticado."}`; es lo esperado al abrir un endpoint protegido en el navegador.

### Auditoría (ODON-222)

`audit_events` no admite cambios ni borrados (trigger). Para comprobar que nadie alteró la auditoría directamente en la base, desde `backend/`:

```powershell
python -m scripts.verify_audit   # sale con 1 si encuentra problemas
```

### Imágenes clínicas y respaldos

Las fotografías se guardan en `IMAGE_STORAGE_DIR` (por defecto `backend/storage/images`, ignorada por Git). Esa carpeta es privada: nunca se sirve como estática ni se copia al repositorio, y los nombres de archivo son aleatorios. Que una foto no tenga nombre no la hace anónima. En desarrollo solo se usan imágenes sintéticas (las pruebas las generan en memoria con Pillow). Para subir una foto el paciente necesita un consentimiento vigente, registrado en la pestaña «Imágenes» de su ficha; al guardarla se recodifica sin metadatos.

Respaldo: `scripts\backup\backup.ps1` respalda la base y la carpeta de imágenes **juntas**, cifradas con restic, y `restore-check.ps1` ensaya la restauración (ODON-226; procedimiento completo en [`BACKUPS.md`](BACKUPS.md)). Después de restaurar, o periódicamente:

```powershell
cd backend
python -m scripts.verify_images
```

El script solo lee. Termina en `0` si base y carpeta coinciden; si no, lista por clave e id (sin datos del paciente) los registros sin archivo, los archivos alterados (SHA-256 distinto), los archivos sin registro y los ajenos (p. ej. temporales de una escritura interrumpida). Las pruebas usan una carpeta temporal y nunca tocan `IMAGE_STORAGE_DIR`.

`python -m scripts.verify_fresh_install` (ODON-276) comprueba, también en modo de solo lectura, que una instalación recién creada con `bootstrap_clinic` solo tiene la clínica y la administración y la carpeta de imágenes vacía. Se usa al pasar de la instalación de prueba a la definitiva (`DEPLOYMENT.md`); en desarrollo, con datos del seed, siempre reportará filas de más.

### Pruebas automatizadas del backend

Las pruebas usan una base PostgreSQL separada cuyo nombre **debe terminar en `_test`**: vacían sus tablas antes de cada prueba y aplican las migraciones con Alembic. Nunca apuntes `TEST_DATABASE_URL` a la base de desarrollo.

```powershell
# Una sola vez: crear la base de pruebas en el contenedor
docker exec odontonet-db createdb -U odontonet odontonet_test

# En backend/, con odonto_venv activo
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pytest --cov            # con cobertura (más lento; es lo que corre CI)
```

**Cobertura (ODON-210):** `backend/.coveragerc` mide `app/` con ramas y exige un mínimo de 95 % (al introducirla era 98 %). En CI la suite corre con `--cov`, así que una caída de cobertura hace fallar el push. Localmente no hace falta en cada cambio: es bastante más lenta. Usa `--cov` solo con la suite completa: con un subconjunto (`-m …`) la cobertura queda por debajo del mínimo y la ejecución falla aunque las pruebas pasen.

#### Categorías

Cada prueba pertenece al menos a una categoría (marcador de pytest), según el objeto que prueba. `python -m pytest` corre todas; con `-m` se elige una categoría o una combinación:

| Categoría | Qué prueba |
| --- | --- |
| `auth` | Login, tokens, `/auth/me`, usuarios inactivos |
| `patients` | Endpoints y validación de pacientes |
| `doctors` | Endpoints de doctores |
| `users` | Gestión de usuarios por administración (`/users`, `/auth/register`) |
| `api` | Contrato: OpenAPI, `/health`, formato de errores |
| `seed` | Seed sintético de desarrollo |
| `isolation` | Aislamiento entre clínicas (transversal) |
| `rbac` | Permisos por rol (transversal) |
| `appointments` | Modelo, integridad y endpoints de citas |
| `records` | Expediente clínico: historia médica, consultas, plan de tratamiento e historial cronológico |
| `images` | Imágenes clínicas: almacenamiento privado, subida y saneamiento, consentimiento, galería y miniaturas, metadatos con revisiones, anulación, auditoría de acceso, verificación de respaldos |
| `periodontal` | Periodontograma manual: modelo y restricciones, validación por pieza y sitio, borradores con revisiones, finalización, anulación, resumen, historial cronológico y reporte PDF |
| `dashboard` | Panel de inicio y reportes: indicadores, periodo en la zona de la clínica, filtro por doctor, agenda de hoy, series por día/semana/mes, CSV, aislamiento y roles |
| `backup` | Manifiesto de respaldos: conteos, versión y final de la cadena de auditoría; detecta restauraciones incompletas |
| `deployment` | Configuración por ambientes, arranque en producción, comprobación de migraciones y alta de la primera clínica |
| `migrations` | Cadena completa de migraciones (una sola cabeza; subir, bajar a la base vacía y volver a subir; `alembic check`) sobre una base temporal `<base>_test_migrations` |

```powershell
python -m pytest -m auth                      # solo autenticación
python -m pytest -m "patients and isolation"  # pacientes entre clínicas
python -m pytest -m "not seed"                # todo excepto el seed
python -m pytest --markers                    # listar categorías
```

Una prueba sin categoría o con un marcador mal escrito detiene la ejecución con un error.

#### Qué correr según el cambio

Durante el desarrollo y al verificar un ticket basta con las categorías del área tocada; la suite completa corre en GitHub Actions en cada push y al cerrar una épica. En cada entrega, el asistente indica el comando exacto.

| Si cambia... | Backend | Frontend |
| --- | --- | --- |
| Login, sesión, contraseñas, límite de intentos, cabeceras y CORS (`auth_routes`, `app/auth/`, `core/password_policy.py`, `services/rate_limit_service.py`, `main.py`) | `python -m pytest -m "auth or users or rbac or api"` | `npx vitest run src/pages/Auth src/pages/Account src/services src/context` |
| Usuarios (`/users`) | `python -m pytest -m "users or rbac"` | `npx vitest run src/pages/Users src/components/users` |
| Pacientes | `python -m pytest -m "patients or isolation"` | `npx vitest run src/pages/Patients src/components/patients` |
| Historia médica / expediente | `python -m pytest -m "records or rbac"` | `npx vitest run src/components/patients src/pages/Patients src/auth` |
| Imágenes clínicas y consentimiento (`image_*`, `patient_image_*`, `photo_consent_*`, `verify_images`) | `python -m pytest -m "images or rbac or records"` | `npx vitest run src/components/patients src/pages/Patients src/auth` |
| Periodontograma (`periodontal_*`) | `python -m pytest -m "periodontal or rbac or isolation"` | `npx vitest run src/components/periodontal src/pages/Patients` |
| Panel de inicio y reportes (`dashboard_*`, `report_*`) | `python -m pytest -m "dashboard or patients"` | `npx vitest run src/pages/Dashboard src/pages/Reports src/components/dashboard` |
| Doctores y horarios | `python -m pytest -m "doctors or appointments"` | `npx vitest run src/pages/Doctors src/components/doctors src/pages/Agenda` |
| Agenda y citas | `python -m pytest -m "appointments or doctors"` | `npx vitest run src/pages/Agenda src/components/appointments` |
| Clínica | `python -m pytest -m isolation` | `npx vitest run src/pages/Clinic` |
| Respaldos (`backup_manifest`, `scripts/backup/`) | `python -m pytest -m backup` y un ensayo con `restore-check.ps1` (ver `BACKUPS.md`) | — |
| Investigación de IA (`ai-service/research/`, `ai-service/tests/`) | En `ai-service/`, con su propio entorno: `.venv\Scripts\python -m pytest` (ver `ai-service/README.md`; no corre en CI porque necesita el entorno de investigación) | — |
| Auditoría (`audit_*`, cualquier operación que registra eventos) | `python -m pytest -m "records or rbac or isolation"` | `npx vitest run src/pages/Audit` |
| Permisos (`permissions.py` / `permissions.ts`) | `python -m pytest -m "rbac or isolation"` | `npx vitest run src/auth src/config src/routes` |
| Seed | `python -m pytest -m seed` | — |
| Despliegue (`compose.prod.yml`, `deploy/`, `scripts/deploy/`) | `bash scripts/deploy/smoke.sh` | — |
| Rutas o esquemas de la API | `python -m scripts.export_openapi` y `python -m pytest -m api` (`docs/openapi.json`, que se usa porque en producción `/docs` está apagado) | — |
| Configuración y despliegue (`core/settings.py`, `core/startup.py`, `bootstrap_clinic`, `verify_fresh_install`) | `python -m pytest -m deployment` | — |
| Migración nueva, modelo compartido, `conftest.py`, `core/errors.py` | `python -m pytest` (completa) | — |
| Componentes base (`components/basic`), `api.ts`, dependencias | — | `npm test` (completa) |

Atajos útiles:

```powershell
python -m pytest --lf                 # solo las que fallaron la vez anterior
python -m pytest -x                   # se detiene en el primer fallo
python -m pytest tests/test_auth.py   # un archivo
python -m pytest -k "reset and not admin"   # por nombre
npx vitest related src/pages/Auth/LoginPage.tsx --run   # pruebas que importan ese archivo
```

**Velocidad (CAL-ENH03):** antes de cada prueba se vacían las tablas con `DELETE` en orden inverso de dependencias y se reinician las secuencias. Es unas 15 veces más barato que `TRUNCATE ... CASCADE`, que recrea los archivos de cada tabla. Las conexiones de pytest usan `synchronous_commit=off` (sin esperar al disco en cada commit), algo inocuo en una base de pruebas. La lista de tablas sale de los modelos, así que una tabla nueva se limpia sola. Para ver qué tarda: `python -m pytest --durations=15`.

La URL de pruebas se deriva de `DATABASE_URL` en `backend/.env` cambiando el nombre de la base a `<nombre>_test`; no hace falta escribir la contraseña. Para usar otra base, define `TEST_DATABASE_URL`. Si la conexión falla, pytest muestra el error completo y cómo crear la base.

Las pruebas usan bcrypt con costo 4 (`BCRYPT_ROUNDS`, fijado en `tests/conftest.py`) para que la suite completa tarde segundos; la aplicación usa 12. Los hashes guardan su propio costo, así que ambos se verifican igual.

### Integración continua (GitHub Actions)

`.github/workflows/ci.yml` se ejecuta en cada push a `main` y en cada pull request, en servidores de GitHub: backend contra un PostgreSQL 16 temporal, con cobertura mínima de 95 % y la cadena completa de migraciones, y frontend con `lint`, `test` y `build`. En pull requests y a mano (*Run workflow*) corre además el job `e2e` (Playwright), y en cada push el job de seguridad (`pip-audit`, `npm audit`, gitleaks). El resultado aparece como ✔ o ✖ junto al commit en GitHub (pestaña *Actions*). Se puede lanzar a mano con *Run workflow*. No usa secretos reales ni la base local.

**Qué correr y cuándo:**

| Momento | Quién | Qué |
| --- | --- | --- |
| Al entregar un ticket | Asistente | Suite completa, E2E y build |
| Al verificar un ticket | Desarrollador | Las categorías del área tocada (ver «Qué correr según el cambio»); `lint`/`build` solo si cambió el frontend; prueba manual |
| En cada push | GitHub Actions | Todo, automáticamente; revisar que quede en ✔ |
| En cada pull request y a mano (*Run workflow*) | GitHub Actions | Además, las pruebas E2E (job `e2e`) |
| Al cerrar una épica | Desarrollador | Suite completa, `lint`, `build`, `npm run e2e` y `verify-infra.ps1` |

## 4. Frontend

En otra terminal desde la raíz:

```powershell
cd frontend
npm ci
npm run dev
```

Abrir http://localhost:5173 (no `127.0.0.1`: la sesión valida el origen contra `FRONTEND_URL`). El frontend llama a `/api` y Vite lo reenvía al backend en `http://127.0.0.1:8000`, como hará el proxy en producción; si el backend está en otro puerto, copia `frontend/.env.example` a `frontend/.env` y define `VITE_API_PROXY` (requiere reiniciar `npm run dev`).

Para comprobar pruebas, compilación y lint:

```powershell
npm test            # pruebas unitarias (Vitest + Testing Library)
npm run e2e         # pruebas de extremo a extremo (Playwright), ver «Pruebas de extremo a extremo»
npm run test:watch  # modo continuo mientras se desarrolla
npm run lint
npm run build
```

Las pruebas viven junto al código (`*.test.ts(x)`); `src/test/renderWithAuth.tsx` permite renderizar componentes con una sesión simulada de cualquier rol.


### Pruebas de extremo a extremo (ODON-214)

Playwright (`frontend/e2e/`, Chromium) recorre los flujos principales contra la API real: inicio de sesión con los tres roles, alta y búsqueda de pacientes, agenda, expediente (consulta y tratamiento en el historial), estados vacíos, 404 de otra clínica y «Acceso denegado». Cada corrida recrea una base propia `odontonet_e2e_test`, aplica las migraciones y carga el seed sintético con una contraseña de prueba; levanta la API en el puerto 8001 y Vite en el 5174, así que no choca con los servidores de desarrollo ni toca la base `odontonet`. Requiere Docker en ejecución y, la primera vez, `npx playwright install chromium`.

```powershell
# En frontend/
npm run e2e                              # todo (~1 min)
npx playwright test e2e/agenda.spec.ts  # un archivo
npx playwright show-report              # informe y trazas de un fallo
```

En CI corren solo en pull requests y a mano (decisión del desarrollador: tardan más que las unitarias).

### Manual de usuario (ODON-242)

`docs/manual/` tiene el manual por rol. Si cambia una pantalla, regenera sus capturas con `npm run manual:capturas` (base propia, datos sintéticos). `npm run manual:pdf` escribe los PDF en `docs/manual/pdf/`, que Git ignora.

## 5. Datos iniciales

Alembic crea las tablas, pero no crea usuarios ni clínicas. Para desarrollo existe un seed sintético versionado, `backend/scripts/seed_dev.py`:

```powershell
# En backend/, con odonto_venv activo
$env:SEED_PASSWORD = "<contraseña de al menos 8 caracteres>"
python -m scripts.seed_dev
```

- Crea **Clínica Demo Norte** y **Clínica Demo Sur**, cada una con administración, recepción, dos doctores y 15 pacientes ficticios. Sirve para probar roles y aislamiento entre clínicas.
- Agrega una **agenda demo** por clínica (60 citas en días hábiles, de 3 días antes a 10 días después de la fecha de ejecución): pasadas atendidas o «No asistió», futuras programadas, confirmadas o canceladas. Solo se crea si la clínica todavía no tiene citas, para no cruzarse con una agenda existente. Para regenerarla, borra las citas de la base de desarrollo y vuelve a correr el seed.
- Registra un **horario demo** (lunes a viernes, 08:00–13:00 y 14:00–18:00) a los doctores que todavía no tienen horario; no toca horarios existentes.
- Es **idempotente**: si se ejecuta de nuevo, no duplica nada. Tampoco borra ni modifica datos existentes.
- Solo corre contra una base **local** (`localhost`/`127.0.0.1`) y con `APP_ENV` igual a `development` (valor por defecto).
- No contiene contraseñas: todos los usuarios demo usan la de `SEED_PASSWORD`. Los correos se imprimen al terminar (por ejemplo, `admin.norte@odontonet-demo.com`).

Un `seed.py` personal en `backend/scripts/` sigue ignorado por Git. La primera clínica real se crea con `scripts/bootstrap_clinic.py` (ver `DEPLOYMENT.md`); el alta de más clínicas en una instalación se planifica aparte con el rol `superadmin`.

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

Checklist antes de commitear una migración:

1. Revisar el archivo generado: nombres de restricciones, ausencia de `drop_table`/`drop_column` no deseados y migración de datos existentes (por ejemplo, valores vacíos antes de una restricción única).
2. Escribir un `downgrade()` que revierta exactamente el `upgrade()` o documentar por qué no es posible.
3. `alembic upgrade head` y `alembic check` (sin operaciones pendientes).
4. `python -m pytest`: las pruebas aplican todas las migraciones sobre la base `_test`.
5. `python -m pytest -m migrations` (también corre en CI) y, en Windows, `scripts\dev\verify-infra.ps1`: prueban la cadena completa en una base vacía temporal.

## 7. Comprobaciones rápidas

Verificación automática de PostgreSQL, Docker y migraciones (reinicia el contenedor una vez y usa una base temporal; no modifica datos):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\verify-infra.ps1
```

Comprobaciones manuales:

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
| `401 No autenticado.`                 | Falta encabezado `Authorization: Bearer <JWT>`.                              |
| `alembic current` distinto de `heads` | Migraciones pendientes; revisar antes de aplicar.                            |
| `IntegrityError` con `clinic_id`      | Base sin migrar: ejecutar `alembic upgrade head`; no desactivar la FK.       |
| CORS bloqueado                        | Agregar el origen del frontend a `CORS_ORIGINS` en `backend/.env`.           |
| `npm ci` → `EPERM ... unlink *.node`  | Un proceso usa `node_modules` (`npm run dev`, Vitest, VS Code). Detenerlo, cerrar esa terminal y repetir `npm ci`. |
| `EBADENGINE` al instalar              | Node.js anterior a lo indicado en `engines`; actualizar Node (ver Requisitos). |
| La salida de npm no aparece en `logs/terminal` | PowerShell 5.1 no transcribe lo que los programas externos escriben directo en consola; usar `npm test 2>&1 \| Out-Host`. |

## 9. Seguridad operativa

- Contraseñas (ODON-230): al menos 10 caracteres y no una de las filtradas más comunes (también `SEED_PASSWORD`); las cuentas existentes la cumplen en su próximo cambio.
- CI revisa en cada push `npm audit --omit=dev`, secretos con gitleaks (`.gitleaks.toml`) y `pip-audit` (bloqueante y sin excepciones desde ODON-264).
- `SECRET_KEY` debe tener al menos 32 bytes; genera una con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. `ALLOWED_HOSTS` lista los hosts a los que se puede dirigir la API (por defecto `localhost,127.0.0.1`; en el despliegue, el dominio real).

No desplegar públicamente el backend actual. Antes de usar datos reales deben completarse aislamiento por clínica, autorización, validación de entradas, auditoría y políticas de privacidad/retención. No compartir capturas de tokens ni archivos `.env`.
