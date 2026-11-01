# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

**Última actualización:** 2026-11-01 — ODON-78 (relación User–Doctor) en Testing.

## Alcance

Sistema de gestión odontológica multi-clínica, con colaboración entre usuarios de la misma clínica. MVP inicial sin IA. Posteriormente, microservicio independiente para asistencia al periodontograma.

## Stack comprobado

- React 19, Vite 8.3, TypeScript (strict), Tailwind CSS 3, React Router 7.18, Axios 1.21, TanStack Query.
- Python 3.11, FastAPI 0.103.2, Pydantic 1.10.13, SQLAlchemy 2, Alembic, pytest.
- PostgreSQL 16 y Docker Compose.

## Estado verificado

- **Calidad:** 166 pruebas backend (login, `/auth/me`, aislamiento entre clínicas, roles, gestión y desactivación de usuarios, listado e integridad de doctores, contrato de API, seed). Frontend: 49 pruebas unitarias (Vitest), `lint` y `build` sin errores, 0 vulnerabilidades npm en producción, pruebas E2E de sesión y de gestión de usuarios.
- **Seguridad:** aislamiento por `clinic_id` del token (ODON-62); RBAC con `require_roles` (ODON-66); usuarios inactivos bloqueados; errores unificados en español sin trazas (ODON-22).
- **Infraestructura:** Docker healthy, persistencia y puerto local verificados con `scripts/dev/verify-infra.ps1` (ODON-26). Migraciones lineales `e7aac1fc989e` → `4c1d2e8f9a10` → `7b3e9d2c5a61`, probadas desde base vacía (ODON-30) y con `alembic check` sin diferencias.
- **Datos de desarrollo:** `backend/scripts/seed_dev.py`, idempotente y solo local (ODON-34).

## Riesgos y deuda técnica

1. **Historial de Git:** un `.env` antiguo (commit `7081a3d`) contiene la `DATABASE_URL` de desarrollo. Mitigado: la contraseña se rotó el 2026-10-31. No se reescribe el historial sin autorización.
2. **Sesión:** resuelta en frontend (ODON-46, ODON-50). Pendiente para producción: refresh token rotativo en cookie `httpOnly`, CSP y revocación del lado del servidor (decisión ODON-52, ver `ARCHITECTURE.md`).
3. **Gestión de personal:** alta, edición y desactivación listas (ODON-86, ODON-94); faltan perfil de doctor desde la interfaz (ODON-90) y alta de la primera clínica (ODON-74). El token se identifica por correo: cambiar el correo cierra la sesión de ese usuario; evaluar usar el id en `sub` junto con ODON-230.
4. **Frontend:** layout sin versión móvil.
5. **Dependencias de desarrollo:** aviso moderado de `minimatch` (<11.0.1) vía ESLint, publicado después de ODON-15; npm lo reporta como 12 moderadas porque cuenta cada paquete de la cadena de ESLint. Solo afecta herramientas de desarrollo (producción: 0 vulnerabilidades). No hay corrección compatible (ESLint 10.14 aún usa minimatch 10) y `npm audit fix --force` degradaría `typescript-eslint`: revisar al actualizar ESLint.
6. **Dependencias:** `requirements.txt` es un `pip freeze` completo (incluye `pydantic-core`, que Pydantic 1 no usa); conviene separar dependencias directas. FastAPI 0.103/Starlette usan el atajo `app=` de httpx y el módulo `multipart` antiguo: esos dos avisos se silencian en `pytest.ini` hasta actualizar FastAPI. `passlib` usa el módulo `crypt` (se elimina en Python 3.13; solo se ve en Linux): revisar antes de cambiar de versión de Python.
7. **Producción:** faltan auditoría, respaldos, endurecimiento y despliegue (épicas CAL y LAN).

## Decisiones vigentes

- La clínica es el límite de aislamiento; la asignación doctor–paciente no restringe acceso.
- Un rol por usuario. `admin` tiene acceso clínico; `receptionist` no accede a expediente, imágenes ni periodontograma ([`PERMISSIONS.md`](PERMISSIONS.md)).
- Interfaz en español.
- Seed versionado `seed_dev.py`; el `seed.py` personal sigue fuera de Git. La importación de datos de clínicas será una funcionalidad aparte.
- Git en Windows con `core.autocrlf=true` (también a nivel de repositorio).

## Jira

- Proyecto `ODON`: 13 épicas, 60 historias, 180 subtareas.
- **ODON-1 Arquitectura e infraestructura — Done:** ODON-14, 18, 22, 26, 30, 34.
- **ODON-3 Clínicas y autorización — In Progress:** ODON-62, ODON-66 y ODON-70 Done; pendientes ODON-58, 74.
- **ODON-5 Pacientes — In Progress:** ODON-106 Done.
- **ODON-2 Autenticación — In Progress:** ODON-38, 42, 46 y 50 Done; pendiente ODON-54 (recuperación de contraseña).
- **ODON-4 Personal y doctores — In Progress:** ODON-82, 86 y 94 Done; ODON-78 Testing; pendiente ODON-90.
- **ODON-11 Calidad:** ODON-254 (categorías de pruebas backend) Done.

## Próximo paso

1. ODON-90 (perfil clínico de doctores), que completa la épica ODON-4.
2. ODON-54 (recuperación de contraseña).

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-<épica> → ODON-<historia> | ... — Estado`.
- El asistente prepara los cambios y los mensajes de commit; el desarrollador realiza los commits y el push.
- El board de Jira es Kanban con backlog y la API no permite mover tickets entre ambos: al empezar una épica, el asistente indica que se pase la épica completa del backlog al board; si se adelanta un ticket de otra épica, indica las claves a mover.
- Mover a Done solo con evidencia: pruebas propias más verificación en el entorno local del desarrollador.
- Al cerrar tickets, dejar un comentario de un párrafo en Jira.
