# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

**Última actualización:** 2026-10-31 (cierre de ODON-14).

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

1. **Bloqueante:** `/patients/` y `/doctors/` carecen de control de acceso y filtro por clínica.
2. **Bloqueante:** `/auth/register` no aprovisiona una clínica de forma segura y puede fallar por `clinic_id` obligatorio.
3. **Bloqueante:** la creación de pacientes no deriva `clinic_id` del usuario autenticado.
4. **Seguridad:** el historial público de Git contiene un `.env` antiguo (commit `7081a3d`) con la `DATABASE_URL` de desarrollo, cuya contraseña sigue en uso. Riesgo bajo (base local). Script de rotación preparado en `scripts/dev/rotate-db-password.ps1`; pendiente de ejecutar. No se reescribe el historial sin autorización explícita.
5. **Deuda técnica:** `requirements.txt` es un `pip freeze` completo (incluye dependencias transitivas y `pydantic-core`, que no usa Pydantic 1). Conviene separar dependencias directas en una historia posterior.
6. **Pendiente:** AuthContext v2 con `/auth/me`, verificación de sesión y usuario/clínica actuales.
7. **Pendiente:** CRUD completo, agenda, expedientes, imágenes, periodontograma manual, pruebas y despliegue.
8. **Decisión:** `seed.py` permanece local y excluido de Git; la importación de datos de clínicas será una funcionalidad independiente futura.

## Jira — situación conocida

- Proyecto `ODON`: 13 épicas, 60 historias, 180 subtareas importadas.
- Épica `ODON-1`: arquitectura e infraestructura.
- Historia `ODON-14`: estructura monorepositorio y convenciones — Done (`npm ci` y `npm run dev` verificados en Windows).
- `ODON-15`: auditoría de estructura — Done.
- `ODON-16`: README y convenciones — Done.
- `ODON-17`: `.gitignore` y configuración de secretos — Done.
- Después: historias `ODON-18`, `ODON-22`, `ODON-26`, `ODON-30`, `ODON-34` de la épica de fundación.

## Próximo paso

1. Ejecutar `scripts/dev/rotate-db-password.ps1` y verificar el backend con `alembic current`.
2. Continuar con la auditoría del frontend base (ODON-18).

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-1 → ODON-14 → ODON-XX | ... — Estado`.
- Entregar cambios en orden de ejecución, archivos completos cuando se necesiten.
- Terminar con commits sugeridos y estado de Jira.
- Al cerrar tickets, aportar comentario de Jira de un párrafo.
- Git en Windows usa `core.autocrlf=true` (configurado también a nivel de repositorio) para que las herramientas que acceden desde Linux no vean cambios fantasma de fin de línea.
