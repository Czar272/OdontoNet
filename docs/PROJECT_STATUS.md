# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

**Última actualización:** 2026-11-07 — ODON-9 (periodontograma manual): ODON-182, 186, 190, 194, 198 y 262 (PGR-ENH01, llenado con valores de salud) Done tras verificación manual; pendiente el cierre de la épica.

## Alcance

Sistema de gestión odontológica multi-clínica, con colaboración entre usuarios de la misma clínica. MVP inicial sin IA. Posteriormente, microservicio independiente para asistencia al periodontograma.

## Stack comprobado

- React 19, Vite 8.3, TypeScript (strict), Tailwind CSS 3, React Router 7.18, Axios 1.21, TanStack Query.
- Python 3.11, FastAPI 0.103.2, Pydantic 1.10.13, SQLAlchemy 2, Alembic, Pillow 12.3 (imágenes clínicas), pytest.
- PostgreSQL 16 y Docker Compose.

## Estado verificado

- **Calidad:** 833 pruebas backend (en Windows 832 y 1 omitida, la de permisos POSIX; unos 5 min en Windows) (limpieza con `DELETE`, CAL-ENH03) (periodontograma: modelo, validación por pieza y sitio, borradores, finalización, anulación, historial y reporte PDF; login y «Recuérdame», recuperación y cambio de contraseña, historia médica versionada, consultas clínicas con revisiones y anulación, plan de tratamiento con estados y concurrencia, historial cronológico paginado, `/auth/me`, aislamiento, modelo y datos de clínicas, modelo, listado paginado y búsqueda, ficha, edición y archivo de pacientes, modelo, integridad, API, concurrencia, estados e historial de citas, horario de doctores y zona horaria de la clínica, roles, gestión y desactivación de usuarios, listado, integridad y perfiles de doctores, contrato de API, seed); CI en GitHub Actions en cada push. Frontend: 457 pruebas unitarias (Vitest), `lint` y `build` sin errores, 0 vulnerabilidades npm en producción, pruebas E2E de sesión, recuperación y cambio de contraseña, historia médica (versiones, conflicto de edición, lectura de recepción), consultas clínicas (registro, edición rastreada, anulación, permisos), plan de tratamiento (pieza FDI con odontograma, estados, completar con consulta, cancelar con motivo, historial), historial cronológico (eventos en vivo, páginas de 20, filtros), gestión de usuarios, archivo de pacientes, listado paginado y agenda (crear, cruce, reprogramar, arrastrar, confirmar y cancelar desde «Por confirmar», historial, horario de doctores con sombreado y aviso fuera de horario).
- **Seguridad:** aislamiento por `clinic_id` del token (ODON-62); RBAC con `require_roles` (ODON-66); usuarios inactivos bloqueados; un cambio de contraseña cierra las demás sesiones (ODON-54); errores unificados en español sin trazas (ODON-22).
- **Infraestructura:** Docker healthy, persistencia y puerto local verificados con `scripts/dev/verify-infra.ps1` (ODON-26). Migraciones lineales `e7aac1fc989e` → `4c1d2e8f9a10` → `7b3e9d2c5a61` → `9d4f1a7b2c83` → `b2e6c4a8d915` → `c4f8a1d2e6b3` → `d7a3b9e15c42` → `e5c2f8a9b471` → `f3a7d1c9b264` → `a8c3e5f7b192` → `b5d9e2f4c731` → `c7e1a4b8d520` → `d2f6b8c1e937` → `e9a4c2d7f815` → `f1b7d3e9a264` → `a3c5e7b9d102` → `b7d9f1a3c605` → `dd714ba31e5c` → `41b5876fa104`, probadas desde base vacía (ODON-30) y con `alembic check` sin diferencias.
- **Datos de desarrollo:** `backend/scripts/seed_dev.py`, idempotente y solo local (ODON-34).

## Riesgos y deuda técnica

1. **Historial de Git:** un `.env` antiguo (commit `7081a3d`) contiene la `DATABASE_URL` de desarrollo. Mitigado: la contraseña se rotó el 2026-10-31. No se reescribe el historial sin autorización.
2. **Sesión:** resuelta en frontend (ODON-46, ODON-50). El cambio de contraseña revoca las sesiones previas (ODON-54), pero el logout no. Pendiente para producción: refresh token rotativo en cookie `httpOnly`, CSP y revocación completa del lado del servidor (decisión ODON-52, ver `ARCHITECTURE.md`).
3. **Gestión de personal:** usuarios (alta, edición, desactivación) y perfiles de doctor listos (ODON-86, 94, 90); falta el alta de clínicas por `superadmin`, que se planifica aparte (ODON-74 cubrió la administración básica de la clínica propia). El número de colegiado no se valida como único. El token se identifica por correo: cambiar el correo cierra la sesión de ese usuario; evaluar usar el id en `sub` junto con ODON-230.
4. **Frontend:** layout sin versión móvil.
5. **Dependencias de desarrollo:** aviso moderado de `minimatch` (<11.0.1) vía ESLint, publicado después de ODON-15; npm lo reporta como 12 moderadas porque cuenta cada paquete de la cadena de ESLint. Solo afecta herramientas de desarrollo (producción: 0 vulnerabilidades). No hay corrección compatible (ESLint 10.14 aún usa minimatch 10) y `npm audit fix --force` degradaría `typescript-eslint`: revisar al actualizar ESLint.
6. **Dependencias:** `requirements.txt` es un `pip freeze` completo (incluye `pydantic-core`, que Pydantic 1 no usa); conviene separar dependencias directas. FastAPI 0.103/Starlette usan el atajo `app=` de httpx y el módulo `multipart` antiguo: esos dos avisos se silencian en `pytest.ini` hasta actualizar FastAPI. `passlib` usa el módulo `crypt` (se elimina en Python 3.13; solo se ve en Linux): revisar antes de cambiar de versión de Python.
7. **Producción:** faltan auditoría, respaldos automáticos, endurecimiento y despliegue (épicas CAL y LAN). Las imágenes tienen procedimiento de respaldo y `verify_images.py` (ODON-166) y registro de accesos al original (ODON-178).
8. **Correo y abuso:** sin `SMTP_HOST` los enlaces de recuperación van al log (solo desarrollo; en producción SMTP es obligatorio). El límite de solicitudes es por cuenta, no por IP; un rate limit global queda para la épica CAL.
9. **Retención de imágenes:** sin plazo definido (decisión del 2026-11-04): lo fija la revisión normativa y ética de CAL03 (ODON-218/221). Mientras tanto no se borra ninguna imagen; las erróneas se anulan con motivo.

## Decisiones vigentes

- La clínica es el límite de aislamiento; la asignación doctor–paciente no restringe acceso.
- Un rol por usuario. `admin` tiene acceso clínico y puede tener perfil de doctor; `receptionist` no accede a expediente, imágenes ni periodontograma ([`PERMISSIONS.md`](PERMISSIONS.md)).
- Interfaz en español.
- Seed versionado `seed_dev.py`; el `seed.py` personal sigue fuera de Git. La importación de datos de clínicas será una funcionalidad aparte.
- Git en Windows con `core.autocrlf=true` (también a nivel de repositorio).

## Jira

- Proyecto `ODON`: 13 épicas, 60 historias, 180 subtareas.
- **ODON-1 Arquitectura e infraestructura — Done:** ODON-14, 18, 22, 26, 30, 34.
- **ODON-3 Clínicas y autorización — Done:** ODON-58, 62, 66, 70 y 74.
- **ODON-5 Pacientes — Done:** ODON-98, 102, 106, 110, 114, 118, 122 y 126.
- **ODON-6 Agenda y citas — Done:** ODON-130, 134, 138, 142, 146 y 257 (CIT-ENH01). ODON-258 (CIT-ENH02, ausencias de doctores) se pospuso: queda en el backlog sin épica, con la etiqueta `cit`.
- **ODON-2 Autenticación — Done:** ODON-38, 42, 46, 50, 52, 54 y 255.
- **ODON-7 Expediente clínico — Done (2026-11-03):** ODON-150, 154, 158, 162, 260 (EXP-ENH01, odontograma para elegir la pieza) y 261 (EXP-ENH02, ficha en pestañas). Imágenes y periodontogramas se sumarán al historial en ODON-174 y ODON-194.
- **ODON-8 Imágenes clínicas — Done (2026-11-07):** definida el 2026-11-03 (comentarios en la épica y en ODON-178). ODON-166 (almacenamiento privado), ODON-170 (subida y consentimiento), ODON-174 (galería, miniaturas e historial) y ODON-178 (origen, vista y fecha de toma; archivo inmutable con revisiones de metadatos; anulación con motivo; registro de accesos al original). La retención se difiere a CAL03 (ODON-218/221).
- **ODON-9 Periodontograma manual — In Progress:** definida el 2026-11-07 (comentario en la épica; referencia funcional periodontalchart-online.com con estilo propio). ODON-182 (PGR01: examen en borrador o finalizado, 32 piezas permanentes y 6 sitios normalizados, NIC calculado, revisiones, resumen descriptivo) y ODON-186 (PGR02: editor con grilla por sitio, dibujo SVG propio de margen y bolsa en vivo, captura con teclado, resumen en vivo, guardado con revisión base y aviso de conflicto) y ODON-190 (PGR03: autoguardado, respaldo de sesión y recuperación, finalizar, anular, guardados y copia del examen anterior) y ODON-194 (PGR04: comparación de dos exámenes con cambios ≥ 2 mm resaltados y eventos en el historial cronológico) y ODON-198 (PGR05: reporte PDF de exámenes finalizados con identificación clínica, medidas, dibujo y aviso de que no es diagnóstico) Done (2026-11-07, verificadas por el desarrollador).
- **ODON-4 Personal y doctores — Done:** ODON-78, 82, 86, 90 y 94.
- **ODON-11 Calidad:** ODON-254 (categorías de pruebas backend) Done; ODON-256 (pruebas rápidas y CI) Done; ODON-259 (CAL-ENH03, pytest más rápido y guía por área) Done.

## Próximo paso

1. Planificar y desarrollar ODON-9 (periodontograma manual: PGR01–05), objetivo específico 2 del protocolo.
2. Decisiones de ODON-8: disco privado detrás de `ImageStorage`, JPEG/PNG/WebP ≤ 10 MB recodificadas sin metadatos, consentimiento versionado, archivo inmutable, solo Doctor y Admin; el uso para investigación y el plazo de retención los fijan el protocolo del comité de ética y la revisión de CAL03.
3. El alta de clínicas por `superadmin` se planifica aparte según el modelo de roles aprobado.
4. ODON-258 (ausencias de doctores) queda para después del MVP.

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-<épica> → ODON-<historia> | ... — Estado`.
- El asistente prepara los cambios y los mensajes de commit; el desarrollador realiza los commits y el push.
- El board de Jira es Kanban con backlog y la API no permite mover tickets entre ambos: al empezar una épica, el asistente indica que se pase la épica completa del backlog al board; si se adelanta un ticket de otra épica, indica las claves a mover.
- Mover a Done solo con evidencia: pruebas propias más verificación en el entorno local del desarrollador.
- Al cerrar tickets, dejar un comentario de un párrafo en Jira.
