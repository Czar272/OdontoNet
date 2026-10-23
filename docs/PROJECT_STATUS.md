# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

## Alcance

Sistema de gestión odontológica multi-clínica, con colaboración entre doctores de la misma clínica. MVP inicial sin IA. Posteriormente, microservicio independiente para asistencia al periodontograma.

## Stack comprobado en el repositorio

- React 19, Vite 8, TypeScript, Tailwind CSS 3, React Router 7, Axios, TanStack Query.
- Python 3.11 recomendado, FastAPI 0.103.2, Pydantic 1.10.13, SQLAlchemy 2, Alembic.
- PostgreSQL 16 y Docker Compose.

## Implementado en código (pendiente de auditoría completa)

- Interfaz base, login, dashboard y página de pacientes.
- JWT, `/auth/login`, `/auth/me` y dependencia de usuario actual.
- Modelos Clinic, User, Doctor, Patient y migración `e7aac1fc989e`.
- Endpoints iniciales de listado/creación de doctores y pacientes.
- Filtros de pacientes, componentes UI, notificaciones y React Query.
- Configuración de entorno externalizada y `.gitignore` revisado (ODON-17).

## Limitaciones y riesgos prioritarios

1. **Bloqueante:** `/patients/` y `/doctors/` carecen de control de acceso y filtro por clínica.
2. **Bloqueante:** `/auth/register` no aprovisiona una clínica de forma segura y puede fallar por `clinic_id` obligatorio.
3. **Bloqueante:** la creación de pacientes no deriva `clinic_id` del usuario autenticado.
4. **Pendiente:** AuthContext v2 con `/auth/me`, verificación de sesión y usuario/clínica actuales.
5. **Pendiente:** CRUD completo, agenda, expedientes, imágenes, periodontograma manual, pruebas y despliegue.
6. **Decisión:** `seed.py` permanece local y excluido de Git; la importación de datos de clínicas será una funcionalidad independiente futura.

## Jira — situación conocida

- Proyecto `ODON`: 13 épicas, 60 historias, 180 subtareas importadas.
- Épica `ODON-1`: arquitectura e infraestructura.
- Historia `ODON-14`: estructura monorepositorio y convenciones.
- `ODON-17`: `.gitignore` y configuración de secretos — finalizada y commiteada según confirmación del desarrollador.
- `ODON-16`: actualizar README y convenciones — **In Progress**, documentación preparada; pendiente revisión local y pruebas.
- `ODON-15`: auditoría de estructura — revisión inicial realizada, pendiente cierre formal.
- Después: historias `ODON-18`, `ODON-22`, `ODON-26`, `ODON-30`, `ODON-34` de la épica de fundación.

## Próximo paso

1. Incorporar y revisar los cinco Markdown de ODON-16.
2. Ejecutar la guía de desarrollo en el entorno local y corregir cualquier desajuste.
3. Cerrar ODON-16 en Jira tras validación; después revisar ODON-15 y ODON-14.

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-1 → ODON-14 → ODON-16 | ... — Estado`.
- Entregar cambios en orden de ejecución, archivos completos cuando se necesiten.
- Terminar con commits sugeridos, estado de Jira y viabilidad de continuar en el mismo chat.
- Al cerrar tickets, aportar comentario de Jira de un párrafo.
