# Convenciones de desarrollo — OdontoNet

## Organización

- Mantener el frontend en `frontend/`, la API en `backend/` y la documentación en `docs/`.
- Reservar un servicio de IA independiente para una fase futura; evitar dependencias de ML dentro del backend clínico.
- En backend: `api/` para rutas HTTP, `schemas/` para contratos, `models/` para persistencia, `auth/` para autenticación/autorización y `database/` para sesiones.
- En frontend: `components/basic/` para UI reutilizable, `components/<dominio>/` para componentes específicos, `pages/` para vistas, `services/` para acceso a API y `types/` para tipos compartidos.

## Python / FastAPI

- Python 3.11 como versión de desarrollo recomendada.
- Importaciones internas absolutas desde `app`, por ejemplo `from app.models.patient import Patient`; no usar `from backend.app...` al ejecutar desde `backend/`.
- Nombrar archivos, funciones y variables en `snake_case`; clases en `PascalCase`.
- Validar solicitudes con Pydantic; no exponer hashes ni secretos en respuestas.
- Usar dependencias para sesiones y autorización; cerrar sesiones correctamente.
- Mantener las reglas de acceso en el servidor. No aceptar `clinic_id` del cliente como autoridad para decidir visibilidad.
- Cambios de esquema únicamente mediante migraciones Alembic revisadas.

## React / TypeScript

- Componentes y tipos en `PascalCase`; funciones y variables en `camelCase`.
- Evitar `any`; utilizar tipos explícitos y DTO separados para creación/actualización.
- Centralizar llamadas HTTP en `services/` y utilizar TanStack Query para estado remoto.
- Separar componentes visuales reutilizables de lógica específica del dominio.
- No confiar en guardas de frontend como sustituto de permisos del backend.
- Mantener consistencia de estilos con Tailwind y componentes compartidos.

## Pruebas

- Backend: `python -m pytest` en `backend/` contra una base PostgreSQL `*_test` (nunca la de desarrollo). Todo endpoint nuevo debe probar aislamiento entre clínicas y permisos por rol.
- Cada prueba lleva al menos una categoría (`auth`, `patients`, `doctors`, `users`, `api`, `seed`, `isolation`, `rbac`); un módulo nuevo agrega su categoría en `pytest.ini` y en `TEST_CATEGORIES` de `tests/conftest.py`.
- Las pruebas no dependen de la intercalación de PostgreSQL: al verificar un orden alfabético, usar nombres que ordenen igual con `C.UTF-8` y `en_US.utf8` (por ejemplo, mismo prefijo). La base de Docker usa `en_US.utf8`, que ignora la puntuación al comparar.
- Frontend: `npm test`, `npm run lint` y `npm run build` sin errores antes de cada commit. Una pantalla restringida declara su permiso en `auth/permissions.ts` y se prueba con los tres roles.
- Migraciones: seguir el checklist de `DEVELOPMENT.md` y `scripts/dev/verify-infra.ps1`.

## Seguridad y privacidad

- Nunca subir `.env`, JWT, contraseñas, dumps, fotografías ni datos identificables de pacientes.
- Versionar únicamente `.env.example` con marcadores no secretos.
- Evitar logs de contraseñas o respuestas de autenticación completas.
- La clínica define el límite de aislamiento; los doctores de una misma clínica podrán colaborar según permisos.
- No desplegar la versión actual con datos reales hasta completar los controles pendientes.
- No utilizar `docker compose down -v` para tareas rutinarias.

## Git y commits

- Hacer cambios pequeños y coherentes; comprobar `git status` y `git diff --cached` antes de confirmar.
- Formato sugerido: `tipo(alcance): descripcion breve`.
- Tipos sugeridos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- Ejemplos: `docs: document local development setup`, `fix(auth): validate active user`, `chore(config): externalize database credentials`.
- No incluir archivos locales ni datos sintéticos específicos de una clínica en commits.
- Cada ticket debe tener pruebas acordes con sus criterios de aceptación y comentario breve de cierre en Jira.

## Jira

- Jerarquía: épica → historia → subtarea.
- Flujo: `To Do` → `In Progress` → `Testing` → `Done`.
- Mover a `Done` solo tras verificar criterios de aceptación; el código escrito no equivale a funcionalidad probada.
- Documentar dependencias y decisiones técnicas relevantes en la historia o en `docs/`.
- Priorizar seguridad y aislamiento por clínica antes de expandir módulos clínicos.

## Documentación

- `README.md`: presentación y arranque rápido.
- `ARCHITECTURE.md`: arquitectura real, decisiones y limitaciones.
- `DEVELOPMENT.md`: instalación, ejecución y solución de problemas.
- `CONVENTIONS.md`: reglas del equipo.
- `PROJECT_STATUS.md`: estado conciso y punto de continuidad.
- Actualizar documentación cuando cambien comandos, contratos o decisiones arquitectónicas.
