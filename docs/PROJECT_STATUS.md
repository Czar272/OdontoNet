# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

**Última actualización:** 2026-10-31 (ODON-62 aislamiento por clínica).

## Alcance

Sistema de gestión odontológica multi-clínica, con colaboración entre doctores de la misma clínica. MVP inicial sin IA. Posteriormente, microservicio independiente para asistencia al periodontograma.

## Stack comprobado en el repositorio

- React 19, Vite 8.3, TypeScript, Tailwind CSS 3, React Router 7.18, Axios 1.21, TanStack Query.
- Python 3.11 recomendado, FastAPI 0.103.2, Pydantic 1.10.13, SQLAlchemy 2, Alembic.
- PostgreSQL 16 y Docker Compose.

## Implementado en código (pendiente de auditoría completa)

- Interfaz base, login, dashboard y página de pacientes.
- JWT, `/auth/login`, `/auth/me` y dependencia de usuario actual.
- Modelos Clinic, User, Doctor, Patient y migración `e7aac1fc989e`.
- Endpoints iniciales de listado/creación de doctores y pacientes.
- Filtros de pacientes, componentes UI, notificaciones y React Query.
- Configuración de entorno externalizada y `.gitignore` revisado (ODON-17).

## Auditoría de estructura (ODON-15) — resultados

- Frontend: `npm ci`, `npm run lint` y `npm run build` sin errores.
- Backend: Python 3.11, `pip check` y `compileall` correctos; Alembic sincronizado en `e7aac1fc989e`.
- Dependencias npm: las 15 vulnerabilidades reportadas (11 altas, 3 moderadas, 1 baja; 5 en producción: axios, react-router, react-router-dom, follow-redirects, form-data) se corrigieron con `npm audit fix --package-lock-only`, sin `--force` y sin cambios de versión mayor. `npm audit` y `npm audit --omit=dev` reportan 0 vulnerabilidades; lint y build verificados tras la actualización.
- `backend/requirements.txt` estaba codificado en UTF-16 (generado con `pip freeze >` en PowerShell); se convirtió a UTF-8 sin cambiar paquetes ni versiones.

## Limitaciones y riesgos prioritarios

1. **Resuelto (ODON-62):** `/patients/` y `/doctors/` exigen JWT, filtran por la clínica del token y toman `clinic_id` de la sesión. Correo de paciente único por clínica (migración `4c1d2e8f9a10`). 23 pruebas cruzadas entre dos clínicas.
2. **Resuelto (ODON-66):** `/auth/register` exige rol `admin` y crea el usuario en la clínica del administrador. Pendiente: edición y desactivación de usuarios (ODON-86, ODON-94) y alta de la primera clínica (ODON-74).
3. **Resuelto (ODON-66):** matriz RBAC en `docs/PERMISSIONS.md`, `require_roles` en backend, 403 en español. Usuarios inactivos no pueden iniciar sesión. 53 pruebas backend. Decisiones de módulos futuros confirmadas (admin con acceso clínico; recepción sin datos clínicos).
4. **Seguridad:** el historial público de Git contiene un `.env` antiguo (commit `7081a3d`) con la `DATABASE_URL` de desarrollo. **Mitigado:** la contraseña se rotó el 2026-10-31 con `scripts/dev/rotate-db-password.ps1`, por lo que la credencial del historial ya no es válida. No se reescribe el historial sin autorización explícita.
5. **Deuda técnica:** `requirements.txt` es un `pip freeze` completo (incluye dependencias transitivas y `pydantic-core`, que no usa Pydantic 1). Conviene separar dependencias directas en una historia posterior.
6. **Deuda frontend:** sin manejo de token expirado (401) ni datos de usuario/clínica en sesión; interfaz unificada en español (decisión 2026-10-31); layout sin versión móvil; `PatientForm` no reutiliza `Input`/`Button`.
7. **Pendiente:** AuthContext v2 con `/auth/me`, verificación de sesión y usuario/clínica actuales.
8. **Pendiente:** CRUD completo, agenda, expedientes, imágenes, periodontograma manual, pruebas y despliegue.
9. **Decisión:** `seed.py` permanece local y excluido de Git; la importación de datos de clínicas será una funcionalidad independiente futura.

## Jira — situación conocida

- Proyecto `ODON`: 13 épicas, 60 historias, 180 subtareas importadas.
- Épica `ODON-1`: arquitectura e infraestructura.
- Historia `ODON-14`: estructura monorepositorio y convenciones — Done (`npm ci` y `npm run dev` verificados en Windows).
- Historia `ODON-62`: aislamiento backend por `clinic_id` — Done (23 pruebas verificadas en Windows).
- Historia `ODON-18`: frontend base — Done. `ODON-106` (crear paciente) — Done.
- Historia `ODON-66`: matriz RBAC y guards backend — Done.
- Historia `ODON-22`: contratos API y errores unificados — Testing (63 pruebas backend). Corregido: registro de contraseña en consola en el login, formulario con Enter, logout, rutas comodín, NavLink activo, accesibilidad de Input/Modal, `strict` en TypeScript, `VITE_API_URL`. Verificado con lint, build y 19 pruebas E2E con API simulada.
- `ODON-15`: auditoría de estructura — Done.
- `ODON-16`: README y convenciones — Done.
- `ODON-17`: `.gitignore` y configuración de secretos — Done.
- Después: historias `ODON-18`, `ODON-22`, `ODON-26`, `ODON-30`, `ODON-34` de la épica de fundación.

## Próximo paso

1. ODON-26 / ODON-30: auditoría de PostgreSQL, Docker y migraciones.
2. AUT04 (ODON-50): cerrar sesión en el frontend ante un 401.

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-1 → ODON-14 → ODON-XX | ... — Estado`.
- Entregar cambios en orden de ejecución, archivos completos cuando se necesiten.
- Terminar con commits sugeridos y estado de Jira.
- Al cerrar tickets, aportar comentario de Jira de un párrafo.
- Git en Windows usa `core.autocrlf=true` (configurado también a nivel de repositorio) para que las herramientas que acceden desde Linux no vean cambios fantasma de fin de línea.
