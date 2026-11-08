# 🦷 OdontoNet

> Plataforma web de gestión clínica odontológica, diseñada para evolucionar hacia el análisis periodontal asistido por inteligencia artificial.

**Estado:** desarrollo activo · **Alcance actual:** base del sistema clínico · **IA:** prevista para una fase independiente.

## Descripción

OdontoNet busca centralizar la administración de clínicas odontológicas: personal, pacientes, citas, expedientes, imágenes clínicas y periodontogramas. El proyecto se organiza como un monorepositorio con frontend React, API FastAPI y PostgreSQL. El servicio de inteligencia artificial se desarrollará por separado y se integrará mediante una API cuando esté validado.

Cada clínica es un espacio aislado: la API filtra todos los datos por la clínica del usuario autenticado y aplica permisos por rol (`admin`, `doctor`, `receptionist`) según [`docs/PERMISSIONS.md`](docs/PERMISSIONS.md).

## Estado de las funcionalidades

| Área | Estado actual |
| --- | --- |
| Interfaz React (español), rutas, layout y componentes reutilizables | Implementado |
| Login JWT, `GET /auth/me`, logout, «Recuérdame», recuperación y cambio de contraseña | Implementado |
| Aislamiento por clínica y permisos por rol | Implementado y cubierto por pruebas |
| Alta de usuarios por administrador (`POST /auth/register`) | Implementado, con edición y desactivación |
| Pacientes | Listado paginado, búsqueda, detalle, creación, edición y archivado |
| Doctores | Listado, detalle y alta de perfil (admin) |
| Agenda y citas | Implementado (calendario compartido, estados, horario de doctores) |
| Expediente clínico | Historia médica versionada, consultas clínicas con historial de cambios, plan de tratamiento con estados y odontograma, e historial cronológico |
| Imágenes clínicas | Almacenamiento privado, subida con consentimiento, galería con miniaturas, metadatos con revisiones, anulación y registro de accesos |
| Periodontograma manual | Examen por pieza y sitio con dibujo en vivo, borrador con autoguardado, finalización, comparación y reporte PDF |
| Inicio y reportes | Indicadores de la clínica con filtro por periodo y doctor, agenda de hoy, reportes de citas y pacientes por día, semana o mes, y exportación CSV (administración) |
| IA periodontal | Fuera del MVP inicial; servicio independiente futuro |

**Aviso:** no usar con datos clínicos reales ni desplegar públicamente hasta completar auditoría, privacidad, respaldos, endurecimiento de seguridad y pruebas de aceptación.

## Tecnologías

- **Frontend:** React 19, TypeScript (strict), Vite 8, Tailwind CSS 3, React Router 7, TanStack Query, Axios, FullCalendar (agenda), Recharts (reportes).
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, JWT, Pillow (imágenes clínicas), reportlab (reporte PDF del periodontograma), pytest.
- **Base de datos:** PostgreSQL 16 en Docker Compose.
- **Futuro módulo IA:** servicio independiente; tecnología y contratos pendientes de validación.

Las versiones exactas están en `frontend/package-lock.json` y `backend/requirements.txt`.

## Estructura

```text
OdontoNet/
├── frontend/            # Aplicación React
├── backend/
│   ├── app/             # API FastAPI (api, auth, core, models, schemas, database)
│   ├── alembic/         # Migraciones del esquema
│   ├── scripts/         # seed_dev.py (datos sintéticos de desarrollo)
│   └── tests/           # Pruebas pytest contra PostgreSQL
├── ai-service/          # Reservado para el futuro servicio de IA (sin código)
├── scripts/dev/         # Utilidades locales (rotación de contraseña, verificación)
├── docs/                # Documentación técnica
├── docker-compose.yml   # PostgreSQL para desarrollo
└── .env.example         # Variables de Docker
```

## Inicio rápido (Windows / PowerShell)

**Requisitos:** Git, Docker Desktop con Compose, Python 3.11, Node.js 22.22.2+ (ver `engines` en `frontend/package.json`).

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
# Edita ambos .env con credenciales locales consistentes y una clave JWT aleatoria. No los subas a Git.

docker compose up -d

cd backend
py -3.11 -m venv odonto_venv
.\odonto_venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
alembic upgrade head
$env:SEED_PASSWORD = "<contraseña de al menos 8 caracteres>"
python -m scripts.seed_dev        # clínicas y usuarios de demostración
uvicorn app.main:app --reload

# En otra terminal
cd frontend
npm ci
npm run dev
```

- Frontend: http://localhost:5173 (por ejemplo, `admin.norte@odontonet-demo.com` con la contraseña de `SEED_PASSWORD`)
- API: http://127.0.0.1:8000 · Documentación: http://127.0.0.1:8000/docs · Estado: http://127.0.0.1:8000/health
- Pruebas: `python -m pytest` en `backend/` · Verificación de infraestructura: `scripts\dev\verify-infra.ps1`

Instrucciones detalladas y solución de problemas en [Desarrollo](docs/DEVELOPMENT.md).

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Permisos por rol](docs/PERMISSIONS.md)
- [Entorno de desarrollo](docs/DEVELOPMENT.md)
- [Convenciones](docs/CONVENTIONS.md)
- [Estado técnico y Jira](docs/PROJECT_STATUS.md)
- [Respaldos y restauración](docs/BACKUPS.md)

## Planificación

El trabajo se organiza en Jira bajo el proyecto `ODON` (épica → historia → subtarea). El objetivo inicial es un MVP clínico **sin IA**, seguido de la integración posterior del servicio de análisis periodontal.

## Datos y licencia

No incorporar datos identificables de pacientes a repositorios, issues, logs ni entornos de demostración. El esquema de licenciamiento del proyecto todavía no está definido; no se debe asumir que el código es de uso público o comercial libre.
