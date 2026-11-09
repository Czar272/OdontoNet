# Estado del proyecto — OdontoNet

> Documento de continuidad técnica. Jira es la fuente de verdad de los estados de los tickets y Git es la fuente de verdad del código.

**Última actualización:** 2026-11-08 — ODON-12 (despliegue): ODON-234, 265, 238 y 242 en Testing. Queda ODON-246 (aceptación con un dentista). ODON-11 sigue a la espera de la revisión legal y ética (ODON-218/220).

## Alcance

Sistema de gestión odontológica multi-clínica, con colaboración entre usuarios de la misma clínica. MVP inicial sin IA. Posteriormente, microservicio independiente para asistencia al periodontograma.

## Stack comprobado

- React 19, Vite 8.3, TypeScript (strict), Tailwind CSS 3, React Router 7.18, Axios 1.21, TanStack Query, Recharts 3.10 (reportes), Playwright 1.64 (E2E).
- Python 3.11, FastAPI 0.162, Starlette 1.9, Pydantic 2.14 (ODON-264), PyJWT 2.15, SQLAlchemy 2, Alembic, Pillow 13.0 (imágenes clínicas), pytest.
- PostgreSQL 16 y Docker Compose.

## Estado verificado

- **Calidad:** 1046 pruebas backend (en Windows 1045 y 1 omitida, la de permisos POSIX; cobertura 98 % de líneas y ramas, mínimo 95 % en CI; cadena completa de migraciones en CI; unos 5 min en Windows) (limpieza con `DELETE`, CAL-ENH03) (auditoría persistente con cadena de hashes; endurecimiento: límite de intentos, política de contraseñas, cabeceras y CORS; panel de inicio: indicadores, periodo en la zona de la clínica, filtro por doctor y agenda de hoy; reportes por día, semana o mes con grupos parciales, CSV solo de administración con auditoría y sin fórmulas; periodontograma: modelo, validación por pieza y sitio, borradores, finalización, anulación, historial y reporte PDF; login y «Recuérdame», recuperación y cambio de contraseña, historia médica versionada, consultas clínicas con revisiones y anulación, plan de tratamiento con estados y concurrencia, historial cronológico paginado, `/auth/me`, aislamiento, modelo y datos de clínicas, modelo, listado paginado y búsqueda, ficha, edición y archivo de pacientes, modelo, integridad, API, concurrencia, estados e historial de citas, horario de doctores y zona horaria de la clínica, roles, gestión y desactivación de usuarios, listado, integridad y perfiles de doctores, contrato de API, seed); CI en GitHub Actions en cada push. Frontend: 13 pruebas E2E con Playwright (login con los tres roles, pacientes, agenda, expediente, estados vacíos y errores; en CI en cada pull request y a mano) y 527 pruebas unitarias (Vitest; incluye Auditoría con los tres roles; incluye Inicio: periodo, filtro por doctor y cuadrícula ampliable; Reportes: gráficos con tabla equivalente y CSV de administración), `lint` y `build` sin errores, 0 vulnerabilidades npm en producción, verificaciones manuales en el navegador de sesión, recuperación y cambio de contraseña, historia médica (versiones, conflicto de edición, lectura de recepción), consultas clínicas (registro, edición rastreada, anulación, permisos), plan de tratamiento (pieza FDI con odontograma, estados, completar con consulta, cancelar con motivo, historial), historial cronológico (eventos en vivo, páginas de 20, filtros), gestión de usuarios, archivo de pacientes, listado paginado y agenda (crear, cruce, reprogramar, arrastrar, confirmar y cancelar desde «Por confirmar», historial, horario de doctores con sombreado y aviso fuera de horario).
- **Seguridad:** aislamiento por `clinic_id` del token (ODON-62); RBAC con `require_roles` (ODON-66); usuarios inactivos bloqueados; un cambio de contraseña cierra las demás sesiones (ODON-54); errores unificados en español sin trazas (ODON-22).
- **Infraestructura:** Docker healthy, persistencia y puerto local verificados con `scripts/dev/verify-infra.ps1` (ODON-26). Migraciones lineales `e7aac1fc989e` → `4c1d2e8f9a10` → `7b3e9d2c5a61` → `9d4f1a7b2c83` → `b2e6c4a8d915` → `c4f8a1d2e6b3` → `d7a3b9e15c42` → `e5c2f8a9b471` → `f3a7d1c9b264` → `a8c3e5f7b192` → `b5d9e2f4c731` → `c7e1a4b8d520` → `d2f6b8c1e937` → `e9a4c2d7f815` → `f1b7d3e9a264` → `a3c5e7b9d102` → `b7d9f1a3c605` → `dd714ba31e5c` → `41b5876fa104` → `23ac2035a1f6` → `5f23eb13bd86` → `3ee52e30e5b6` → `8c1f4a2d7b30`, probadas desde base vacía (ODON-30; desde ODON-210 también en CI con `tests/test_migrations.py`) y con `alembic check` sin diferencias.
- **Datos de desarrollo:** `backend/scripts/seed_dev.py`, idempotente y solo local (ODON-34).

## Riesgos y deuda técnica

1. **Historial de Git:** un `.env` antiguo (commit `7081a3d`) contiene la `DATABASE_URL` de desarrollo. Mitigado: la contraseña se rotó el 2026-10-31. No se reescribe el historial sin autorización.
2. **Sesión:** token de acceso en memoria y refresh token rotativo en cookie `httpOnly`, revocable desde el servidor (ODON-265, ver `ARCHITECTURE.md`). La CSP del frontend se aplica en el proxy (ODON-238).
3. **Gestión de personal:** usuarios (alta, edición, desactivación) y perfiles de doctor listos (ODON-86, 94, 90); falta el alta de clínicas por `superadmin`, que se planifica aparte (ODON-74 cubrió la administración básica de la clínica propia). El número de colegiado no se valida como único. El token de acceso se identifica por correo: al cambiar el correo deja de valer y la sesión lo renueva sola; ODON-263 cambió la librería de JWT (PyJWT) sin cambiar `sub`, para no invalidar las sesiones vigentes; usar el id en `sub` sigue siendo una mejora pendiente sin ticket.
4. **Frontend:** layout sin versión móvil.
5. **Dependencias de desarrollo:** aviso moderado de `minimatch` (<11.0.1) vía ESLint, publicado después de ODON-15; npm lo reporta como 12 moderadas porque cuenta cada paquete de la cadena de ESLint. Solo afecta herramientas de desarrollo (producción: 0 vulnerabilidades). No hay corrección compatible (ESLint 10.14 aún usa minimatch 10) y `npm audit fix --force` degradaría `typescript-eslint`: revisar al actualizar ESLint.
6. **Dependencias:** `requirements.txt` es un `pip freeze` completo; conviene separar dependencias directas. `pytest.ini` solo silencia dos avisos del TestClient de Starlette: un alias de anyio y la recomendación de usar httpx2 (se evaluará cuando tenga una versión estable con al menos dos semanas). `passlib` usa el módulo `crypt` (se elimina en Python 3.13; solo se ve en Linux): revisar antes de cambiar de versión de Python. `pip-audit` (ODON-230) encontró vulnerabilidades conocidas en 10 paquetes; ODON-263 y ODON-264 (Pydantic v2, Starlette 1.x) las corrigieron todas: `pip-audit` es bloqueante y sin excepciones. `AllowedHostsMiddleware` (`ALLOWED_HOSTS`) se mantiene como defensa adicional.
7. **Producción:** auditoría (ODON-222), endurecimiento (ODON-230) y respaldos cifrados con ensayo de restauración (ODON-226) listos; el despliegue está listo y probado con la pila real (ODON-238, `DEPLOYMENT.md`); falta instalarlo en la clínica y programar allí los respaldos (`register-tasks.ps1`). Las imágenes tienen procedimiento de respaldo y `verify_images.py` (ODON-166) y registro de accesos al original (ODON-178).
8. **Correo y abuso:** sin `SMTP_HOST` los enlaces de recuperación van al log solo en desarrollo; en producción el correo es opcional y administración asigna la contraseña nueva (ODON-234). El login y la recuperación tienen límite de intentos por cuenta y por IP (ODON-230).
9. **Retención de imágenes:** sin plazo definido (decisión del 2026-11-04): lo fija la revisión normativa y ética de CAL03 (ODON-218/221). Mientras tanto no se borra ninguna imagen; las erróneas se anulan con motivo.
10. **Privacidad (ODON-218):** borrador en `PRIVACY.md` (inventario de datos, acceso mínimo, consentimiento, propuesta de retención y preguntas). Falta la revisión legal (abogado) y ética (comité de la UVG a confirmar con el asesor); no usar datos reales antes.

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
- **ODON-9 Periodontograma manual — Done (2026-11-07):** definida el 2026-11-07 (comentario en la épica; referencia funcional periodontalchart-online.com con estilo propio). ODON-182 (modelo), ODON-186 (editor), ODON-190 (guardado y recuperación), ODON-194 (historial y comparación), ODON-198 (PDF) y ODON-262 (PGR-ENH01, llenado con valores de salud con origen predeterminado). Pendiente con dentistas: margen por defecto del llenado y fuente clínica de los umbrales.
- **ODON-10 Dashboard y reportes — Done (2026-11-07):** definida el 2026-11-07 (comentario en la épica). ODON-202 (panel de inicio: indicadores, filtro por doctor, agenda de hoy; `patients.created_at`) y ODON-206 (reportes de citas y pacientes por día, semana o mes; CSV solo administración).
- **ODON-12 Despliegue y entrega — En curso:** en Testing: ODON-234 (configuración por ambientes), ODON-265 (sesión segura), ODON-238 (despliegue con Docker Compose y HTTPS local) y ODON-242 (manual por rol, `docs/manual/`). Pendiente: ODON-246 (aceptación) y la instalación en una clínica.
- **ODON-4 Personal y doctores — Done:** ODON-78, 82, 86, 90 y 94.
- **ODON-11 Calidad, privacidad y seguridad — En curso:** ODON-254 (categorías de pruebas backend), ODON-256 (pruebas rápidas y CI) y ODON-259 (pytest más rápido y guía por área) Done. Done el 2026-11-08: ODON-210 (cobertura mínima y cadena de migraciones), ODON-214 (E2E con Playwright), ODON-222 (auditoría), ODON-226 (respaldos cifrados y ensayo de restauración), ODON-230 (endurecimiento), ODON-263 (dependencias) y ODON-264 (Pydantic v2). ODON-218 (privacidad) sigue en Testing: su subtarea ODON-220 depende de la revisión legal y ética.

## Próximo paso

1. Prueba del sistema con dos dentistas: recoger mejoras y comentarios y convertirlos en historias.
2. Obtener la revisión legal y ética de `PRIVACY.md` para terminar ODON-218/220 y cerrar ODON-11. Antes de usar datos reales: programar los respaldos en el servidor y ensayar la nube (`BACKUPS.md`).
   Después, la prueba de aceptación ODON-246 con un dentista, solo con datos sintéticos hasta completar ODON-220.
3. El alta de clínicas por `superadmin` se planifica aparte según el modelo de roles aprobado.
4. ODON-258 (ausencias de doctores) queda para después del MVP.

## Convenciones de colaboración

- Encabezar respuestas técnicas con `ODON-<épica> → ODON-<historia> | ... — Estado`.
- El asistente prepara los cambios y los mensajes de commit; el desarrollador realiza los commits y el push.
- El board de Jira es Kanban con backlog y la API no permite mover tickets entre ambos: al empezar una épica, el asistente indica que se pase la épica completa del backlog al board; si se adelanta un ticket de otra épica, indica las claves a mover.
- Mover a Done solo con evidencia: pruebas propias más verificación en el entorno local del desarrollador.
- Al cerrar tickets, dejar un comentario de un párrafo en Jira.
