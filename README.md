# 🦷 OdontoNet

> Plataforma web de gestión clínica odontológica, diseñada para evolucionar hacia el análisis periodontal asistido por inteligencia artificial.

**Estado:** desarrollo activo · **Alcance actual:** base del sistema clínico · **IA:** prevista para una fase independiente.

## Descripción

OdontoNet busca centralizar la administración de clínicas odontológicas: personal, pacientes, citas, expedientes, imágenes clínicas y periodontogramas. El proyecto se organiza como un monorepositorio con frontend React, API FastAPI y PostgreSQL. El servicio de inteligencia artificial se desarrollará por separado y se integrará mediante una API cuando esté validado.

El modelo de datos ya contempla clínicas, usuarios, doctores y pacientes. Los endpoints de pacientes y doctores ya filtran por la clínica del usuario autenticado; la autorización por rol sigue pendiente.

## Estado de las funcionalidades

| Área                                                  | Estado actual                                                  |
| ----------------------------------------------------- | -------------------------------------------------------------- |
| Interfaz React, rutas y componentes reutilizables     | Base implementada                                              |
| Login JWT y `GET /auth/me`                            | Implementados; sesión frontend aún básica                      |
| Clínicas, usuarios, doctores y pacientes              | Modelos relacionales y migración implementados                 |
| Pacientes                                             | Listado y creación inicial; falta CRUD completo y autorización |
| Doctores                                              | Listado y creación inicial; falta autorización y validaciones  |
| Agenda, expedientes, imágenes, periodontograma manual | Pendientes                                                     |
| IA periodontal                                        | Fuera del MVP inicial; servicio independiente futuro           |

**Aviso:** no usar con datos clínicos reales ni desplegar públicamente hasta completar autorización, aislamiento entre clínicas, validaciones, auditoría, privacidad y pruebas de seguridad.

## Tecnologías

- **Frontend:** React 19, TypeScript, Vite 8, Tailwind CSS 3, React Router 7, TanStack Query, Axios.
- **Backend:** Python 3.11 recomendado, FastAPI, SQLAlchemy 2, Pydantic 1, Alembic, JWT.
- **Base de datos:** PostgreSQL 16 en Docker Compose.
- **Futuro módulo IA:** servicio independiente; tecnología y contratos pendientes de validación.

Las versiones exactas de dependencias están en `frontend/package-lock.json` y `backend/requirements.txt`.

## Estructura

```text
OdontoNet/
├── frontend/                 # Aplicación React
├── backend/                  # API FastAPI y migraciones Alembic
│   ├── app/
│   └── alembic/
├── database/                 # Material auxiliar (no es la fuente de migraciones)
├── docs/                     # Documentación técnica
├── docker-compose.yml       # PostgreSQL para desarrollo
├── .env.example              # Ejemplo de variables para Docker
└── README.md
```

`ai-service/` es una carpeta prevista para una etapa futura; puede no estar incluida en el repositorio actual.

## Inicio rápido (Windows / PowerShell)

**Requisitos:** Git, Docker Desktop con Compose, Python 3.11, Node.js y npm compatibles con el `package.json` actual.

Desde la raíz del repositorio:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

Edita ambos archivos `.env` con credenciales locales consistentes y una clave JWT aleatoria. **No subas esos archivos a Git.**

```powershell
docker compose config --quiet
docker compose up -d
docker compose ps
```

En otra terminal:

```powershell
cd backend
py -3.11 -m venv odonto_venv
.\odonto_venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

En una tercera terminal:

```powershell
cd frontend
npm ci
npm run dev
```

- Frontend: http://localhost:5173
- API: http://127.0.0.1:8000
- Documentación de API: http://127.0.0.1:8000/docs

El repositorio **no proporciona un aprovisionamiento de administrador listo para producción**. El inicio de sesión requiere un usuario existente en la base. No utilizar el endpoint público de registro actual para aprovisionamiento real hasta implementar los controles de clínica y permisos.

Para instrucciones detalladas y resolución de problemas, consulta [Desarrollo](docs/DEVELOPMENT.md).

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Entorno de desarrollo](docs/DEVELOPMENT.md)
- [Convenciones](docs/CONVENTIONS.md)
- [Estado técnico y Jira](docs/PROJECT_STATUS.md)

## Planificación

El trabajo se organiza en Jira bajo el proyecto `ODON`, con épicas, historias y subtareas. El objetivo inicial es un MVP clínico **sin IA**, seguido de una integración posterior del servicio de análisis periodontal.

## Datos y licencia

No incorporar datos identificables de pacientes a repositorios, issues, logs ni entornos de demostración. El esquema de licenciamiento del proyecto todavía no está definido; no se debe asumir que el código es de uso público o comercial libre.
