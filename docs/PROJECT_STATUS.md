# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

**Última actualización:** 2026-10-31 — cierre de la épica ODON-1 (Arquitectura e infraestructura).

## Alcance

Sistema de gestión odontológica multi-clínica, con colaboración entre usuarios de la misma clínica. MVP inicial sin IA. Posteriormente, microservicio independiente para asistencia al periodontograma.

## Stack comprobado

- React 19, Vite 8.3, TypeScript (strict), Tailwind CSS 3, React Router 7.18, Axios 1.21, TanStack Query.
- Python 3.11, FastAPI 0.103.2, Pydantic 1.10.13, SQLAlchemy 2, Alembic, pytest.
- PostgreSQL 16 y Docker Compose.

## Estado verificado

- **Calidad:** 75 pruebas backend (aislamiento entre clínicas, roles, contrato de API, seed) verificadas en Windows. Frontend: `lint` y `build` sin errores; 0 vulnerabilidades npm.
- **Seguridad:** aislamiento por `clinic_id` del token (ODON-62); RBAC con `require_roles` (ODON-66); usuarios inactivos bloqueados; errores unificados en español sin trazas (ODON-22).
- **Infraestructura:** Docker healthy, persistencia y puerto local verificados con `scripts/dev/verify-infra.ps1` (ODON-26). Migraciones lineales `e7aac1fc989e` → `4c1d2e8f9a10`, probadas desde base vacía (ODON-30).
- **Datos de desarrollo:** `backend/scripts/seed_dev.py`, idempotente y solo local (ODON-34).

## Riesgos y deuda técnica

1. **Historial de Git:** un `.env` antiguo (commit `7081a3d`) contiene la `DATABASE_URL` de desarrollo. Mitigado: la contraseña se rotó el 2026-10-31. No se reescribe el historial sin autorización.
2. **Sesión en frontend:** sin restauración con `/auth/me` ni reacción a `401`; JWT en `localStorage` (ODON-46, ODON-50).
3. **Gestión de personal:** sin edición/desactivación de usuarios ni alta de la primera clínica (ODON-86, ODON-94, ODON-74).
4. **Frontend:** layout sin versión móvil; navegación no adaptada al rol (ODON-70).
5. **Dependencias:** `requirements.txt` es un `pip freeze` completo (incluye `pydantic-core`, que Pydantic 1 no usa); conviene separar dependencias directas.
6. **Producción:** faltan auditoría, respaldos, endurecimiento y despliegue (épicas CAL y LAN).

## Decisiones vigentes

- La clínica es el límite de aislamiento; la asignación doctor–paciente no restringe acceso.
- Un rol por usuario. `admin` tiene acceso clínico; `receptionist` no accede a expediente, imágenes ni periodontograma ([`PERMISSIONS.md`](PERMISSIONS.md)).
- Interfaz en español.
- Seed versionado `seed_dev.py`; el `seed.py` personal sigue fuera de Git. La importación de datos de clínicas será una funcionalidad aparte.
- Git en Windows con `core.autocrlf=true` (también a nivel de repositorio).

## Jira

- Proyecto `ODON`: 13 épicas, 60 historias, 180 subtareas.
- **ODON-1 Arquitectura e infraestructura — Done:** ODON-14, 18, 22, 26, 30, 34.
- **ODON-3 Clínicas y autorización — In Progress:** ODON-62 y ODON-66 Done; pendientes ODON-58, 70, 74.
- **ODON-5 Pacientes — In Progress:** ODON-106 Done.
- **ODON-2 Autenticación — To Do.**

## Próximo paso

1. ODON-46 (AuthContext v2: restaurar sesión con `/auth/me`) y ODON-50 (logout y manejo de token expirado).
2. ODON-70 (navegación y rutas por rol en el frontend).

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-<épica> → ODON-<historia> | ... — Estado`.
- El asistente prepara los cambios y los mensajes de commit; el desarrollador realiza los commits y el push.
- Mover a Done solo con evidencia: pruebas propias más verificación en el entorno local del desarrollador.
- Al cerrar tickets, dejar un comentario de un párrafo en Jira.
