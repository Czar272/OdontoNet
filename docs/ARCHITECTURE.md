# Arquitectura de OdontoNet

## Propósito y límites

OdontoNet es un monorepositorio con una aplicación web, una API clínica y una base PostgreSQL. La IA periodontal será un servicio independiente y no forma parte del MVP clínico inicial.

```text
Navegador
   │ HTTP
   ▼
React + TypeScript (frontend/)
   │ REST / JSON + JWT
   ▼
FastAPI (backend/app/)
   │ SQLAlchemy
   ▼
PostgreSQL 16 (Docker Compose)

[Futuro: servicio IA] ← API clínica / contrato por definir
```

## Módulos existentes

### Frontend

- `src/pages/`: inicio de sesión, recuperación y cambio de contraseña, inicio (dashboard), agenda, pacientes, doctores, usuarios y clínica. Interfaz en español.
- `src/pages/Agenda/`: calendario compartido de la clínica con FullCalendar 6 (MIT: vistas de mes, semana y día, más el plugin de interacción). Se carga con `React.lazy` en un archivo aparte. Pide al backend solo el rango visible, filtra por doctor en el backend y por estado en el navegador, y muestra las horas en la hora local del navegador. Seleccionar un horario abre «Nueva cita»; arrastrar o estirar una cita pendiente y futura la reprograma, y si el backend responde 409 vuelve a su lugar. Cada doctor tiene un color estable (`agendaColors.ts`, según el orden de los ids y distinto de los colores de estado): la cita lleva fondo claro y franja de ese color, arriba el nombre del doctor (corto en la semana, y solo sus iniciales en columnas muy angostas, mediante una container query en `index.css`), luego el paciente y la hora con un punto del color de su estado. Las citas simultáneas se muestran una al lado de la otra (`slotEventOverlap={false}`), y la leyenda de doctores filtra con un clic. Las columnas por doctor (vista de recursos) son una función de pago de FullCalendar; la alternativa gratuita es la vista de día, que ocupa todo el ancho.
- `src/routes/`: router, ruta protegida (espera la verificación de sesión y recuerda la ruta solicitada), `RequirePermission` (página "Acceso denegado" si el rol no tiene permiso) y ruta comodín.
- `src/auth/permissions.ts`, `src/config/navigation.ts`, `src/hooks/usePermission.ts`: permisos por rol reflejados de `PERMISSIONS.md`; el menú y las acciones se muestran según el rol. El backend sigue siendo la autoridad.
- `src/layouts/`: barra lateral con clínica, usuario, rol, navegación activa y cierre de sesión.
- `src/context/AuthContext.tsx`: sesión con estados `loading` / `authenticated` / `unauthenticated`; restaura usuario y clínica con `/auth/me` al cargar; login, logout y cierre automático ante un `401`.
- `src/services/`: cliente Axios (`VITE_API_URL`) con interceptor de `401`, `session.ts` (token), servicios por recurso y `apiError.ts` para mostrar el `detail` de la API.
- `src/components/basic/`: Button, Input, Select, Textarea, Modal, Table, Card, PageHeader, LoadingSpinner (accesibles); `src/components/<dominio>/`: formularios de pacientes, usuarios, doctores y citas (con buscador de pacientes en el backend). `components/patients/TreatmentsCard.tsx` muestra el plan de tratamiento (pendientes y cerrados, botones según la matriz de estados, modales para completar con consulta, cancelar con motivo e historial). `components/patients/ClinicalVisitsCard.tsx` lista las consultas en orden cronológico, con alta y edición en un modal, anulación con motivo e historial de cambios. `components/patients/MedicalHistoryCard.tsx` muestra la historia médica en la ficha del paciente: edición en dos pasos, selector de versiones anteriores en solo lectura y aviso si otra persona guardó antes.
- `src/types/`: contratos TypeScript mantenidos manualmente.

### Backend

- `app/main.py`: instancia FastAPI, routers, manejadores de error, CORS (`CORS_ORIGINS`) y `/health`.
- `app/api/`: rutas `/auth`, `/clinic`, `/patients`, `/patients/{id}/medical-history`, `/patients/{id}/visits`, `/patients/{id}/treatments`, `/doctors`, `/users`, `/appointments`. `/clinic` no recibe id: siempre opera sobre la clínica de la sesión.
- `app/services/`: reglas de negocio compartidas entre rutas (`user_service.py`: alta y edición de usuarios).
- `app/auth/`: hash de contraseñas, JWT, usuario actual (`get_current_user`), clínica actual (`get_current_clinic_id`) y roles (`permissions.py`, `require_roles`).
- `app/core/errors.py`: formato único de errores.
- Registro: los loggers `odontonet.*` escriben en la consola de uvicorn. `odontonet.audit` anota cambios relevantes (p. ej. `patient.updated`, `patient.doctor_changed`) solo con ids y nombres de campos, nunca datos personales. Es provisional: la auditoría persistente se diseña en ODON-222.
- `app/models/`: Clinic, User, Doctor y Patient.
- `app/schemas/`: modelos de entrada/salida Pydantic.
- `app/database/`: motor SQLAlchemy, sesiones y dependencia de sesión.
- `alembic/`: cambios del esquema; no usar `Base.metadata.create_all` para evolucionar la base.
- `scripts/seed_dev.py`: datos sintéticos de desarrollo; `tests/`: pruebas pytest contra PostgreSQL.

## Relaciones del modelo

```text
Clinic 1 ── * User
Clinic 1 ── * Doctor
Clinic 1 ── * Patient
User   1 ── 0..1 Doctor (misma clínica; garantizado por la base)
Doctor 1 ── * Patient (asignación opcional; misma clínica, garantizado por la base)
Clinic 1 ── * Appointment
Patient 1 ── * Appointment (misma clínica, garantizado por la base)
Doctor  1 ── * Appointment (misma clínica; sin cruces de horario por doctor ni por paciente, garantizado por la base)
Doctor  1 ── * DoctorAvailabilityBlock (horario semanal; misma clínica, garantizado por la base)
```

`Patient.doctor_id` identifica al doctor asignado para organización y filtros. **No define propiedad exclusiva del paciente:** los usuarios autorizados de la misma clínica acceden a sus pacientes según su rol. El correo del paciente es único dentro de cada clínica.

**Integridad Patient–Doctor (ODON-98):** `fk_patients_doctor_clinic` (`patients(doctor_id, clinic_id)` → `doctors(id, clinic_id)`) impide asignar un doctor de otra clínica; con `doctor_id` vacío no aplica, porque el doctor es opcional. El listado carga doctor y usuario con joins (sin consultas N+1, verificado por prueba).

**Citas (ODON-130):** una cita guarda `starts_at` (con zona horaria; la base lo guarda en UTC) y `duration_minutes` (5 a 480). El fin se calcula: en Python con `Appointment.ends_at` y en SQL con la función `appointment_end(starts_at, duration_minutes)`, declarada `IMMUTABLE` porque sumar minutos no depende de la zona horaria. Estados: `scheduled` (Programada), `confirmed` (Confirmada), `completed` (Atendida), `cancelled` (Cancelada) y `no_show` (No asistió). Restricciones:
- `fk_appointments_patient_clinic` y `fk_appointments_doctor_clinic`: paciente y doctor son de la clínica de la cita.
- `ex_appointments_doctor_overlap` y `ex_appointments_patient_overlap` (`EXCLUDE USING gist`, extensión `btree_gist`): ni un doctor ni un paciente tienen dos citas que se crucen mientras ocupen el horario (programada, confirmada o atendida), aunque sean con doctores distintos. Cancelada y No asistió liberan el horario. Los intervalos son `[inicio, fin)`, así que una cita puede empezar justo cuando termina otra. La base lo impide aunque lleguen dos peticiones a la vez; el backend valida antes para dar un mensaje claro y traduce la violación de la base al mismo `409` (`app/services/appointment_service.py`, ODON-134).
- Un paciente o doctor con citas no se borra: las citas son historial.
- Estados y seguimiento (ODON-146): `POST /appointments/{id}/status` aplica la matriz de transiciones de `app/services/appointment_service.py` (reflejada para la interfaz en `frontend/src/pages/Agenda/appointmentStatus.ts`). Cada cambio se guarda en `appointment_status_changes` (FK compuesta a la cita de la misma clínica) en el mismo commit que la cita.
- Horario de doctores (ODON-142): `doctor_availability_blocks` guarda bloques semanales (`weekday` 0 = lunes … 6 = domingo, `start_time`, `end_time` sin zona) con FK compuesta al doctor de la misma clínica y checks de día y de orden. Las horas se interpretan en `clinics.timezone` (IANA; en Windows Python necesita el paquete `tzdata`). `ensure_within_schedule` en `app/services/appointment_service.py` exige que la cita quepa en un bloque del mismo día local; si no, `409` con `outside_schedule`, salvo `allow_outside_schedule`. Sin bloques no se restringe. En el frontend, `agendaSchedule.ts` convierte los bloques al `businessHours` de FullCalendar (que numera desde el domingo).
- Decidido el 2026-11-02: un paciente con citas próximas activas no se puede archivar, y no se crean citas para pacientes archivados (ODON-134). Las horas se guardan en UTC y se muestran en la hora local del navegador.

**Integridad User–Doctor (ODON-78):** `uq_doctors_user_id` impide un segundo perfil para el mismo usuario y `fk_doctors_user_clinic` (`doctors(user_id, clinic_id)` → `users(id, clinic_id)`) impide un perfil en otra clínica que su usuario. Usuarios y doctores no se borran: un usuario con perfil o un doctor con pacientes no se puede eliminar (las FK lo bloquean y el ORM usa `passive_deletes`); el acceso se retira desactivando (ODON-94).

## Decisiones arquitectónicas

1. **Aislamiento por clínica:** todo recurso clínico pertenece a una clínica y toda operación se limita por el `clinic_id` del usuario autenticado (`get_current_clinic_id`). Un `clinic_id` enviado por el navegador se ignora. Un recurso de otra clínica responde `404`.
2. **Roles:** `admin`, `doctor` y `receptionist`, un rol por usuario, aplicados en el backend con `require_roles` y leídos de la base en cada petición. Matriz y decisiones en [`PERMISSIONS.md`](PERMISSIONS.md).
3. **Autenticación:** `POST /auth/login` emite un JWT con expiración configurable; `GET /auth/me` devuelve usuario y clínica. Usuarios inactivos no inician sesión y sus tokens dejan de valer. El frontend guarda el JWT en `sessionStorage` (o en `localStorage` con «Recuérdame») de forma temporal; revisar la estrategia frente a XSS antes de producción.
4. **Migraciones:** Alembic es la fuente de verdad del esquema. Cadena lineal: `e7aac1fc989e` (esquema inicial) → `4c1d2e8f9a10` (correo único por clínica e índices `clinic_id`) → `7b3e9d2c5a61` (User–Doctor uno a uno y misma clínica) → `9d4f1a7b2c83` (doctor del paciente de la misma clínica) → `b2e6c4a8d915` (`patients.archived_at`, archivo de pacientes) → `c4f8a1d2e6b3` (tabla `appointments`, `btree_gist` y `appointment_end`) → `d7a3b9e15c42` (sin cruces de citas por paciente; se detiene si ya hay cruces) → `e5c2f8a9b471` (historial `appointment_status_changes`; su downgrade se detiene si ya hay historial) → `f3a7d1c9b264` (`clinics.timezone` y `doctor_availability_blocks`; su downgrade se detiene si hay horarios registrados). `7b3e9d2c5a61` y `9d4f1a7b2c83` se detienen si hay datos que las violan; los downgrades de `b2e6c4a8d915` y `c4f8a1d2e6b3` se detienen si hay pacientes archivados o citas registradas. Checklist de revisión en `DEVELOPMENT.md`.
5. **Pruebas:** pytest contra una base PostgreSQL `*_test` que aplica todas las migraciones; incluyen aislamiento entre dos clínicas, matriz de roles, contrato de la API y seed.
6. **Separación de IA:** no acoplar PyTorch/OpenCV al backend clínico; definir posteriormente contratos versionados y controles de acceso.
7. **Datos clínicos:** almacenamiento de imágenes, auditoría de accesos y políticas de retención siguen pendientes.
8. **Historia médica versionada (ODON-150):** `patient_medical_histories` guarda una fila por versión (1, 2, 3...) con autor (`created_by_user_id`) y fecha; ninguna se modifica ni se borra, y la vigente es la de mayor versión. Cada guardado envía la historia completa y `base_version` (la versión que se editaba). Si no coincide con la vigente, la API responde `409` con `current_version` en vez de pisar el cambio de otra persona; la restricción única `(patient_id, version)` cubre los guardados simultáneos. Las condiciones médicas son una lista fija en JSONB (`MEDICAL_CONDITIONS`, cada una con `present` sí/no/sin dato y `detail`); hábitos y antecedentes odontológicos son columnas, para poder consultarlos (por ejemplo tabaquismo y diabetes, factores del grado periodontal). Las FKs compuestas aseguran que paciente y autor sean de la clínica de la historia. Un paciente archivado conserva su historia en solo lectura. La auditoría registra `medical_history.created` solo con ids.
9. **Consultas clínicas (ODON-154):** `clinical_visits` guarda el contenido vigente (fecha y hora, doctor, motivo, hallazgos, diagnóstico profesional, procedimientos, indicaciones y próxima cita sugerida) y `clinical_visit_revisions` una copia por guardado con su autor (la revisión 1 es el alta). Editar exige `base_revision` (si no coincide, `409` con `current_revision`) y un guardado sin cambios no crea revisión. Solo quien registró la consulta o administración la edita o la anula; anular exige un motivo, guarda quién y cuándo, y la consulta sigue visible. No hay borrado. La fecha de atención no puede quedar en el futuro y la próxima cita debe ser posterior al día de la consulta en la zona horaria de la clínica. El doctor debe ser un doctor activo de la clínica, salvo que se conserve el que ya tenía la consulta. En las respuestas, `doctor.id` es el id del perfil de doctor (el que se envía como `doctor_id`), no el del usuario. El periodontograma no forma parte de la consulta: tiene su propia épica (ODON-9) y podrá referenciar la consulta en que se tomó.
10. **Plan de tratamiento (ODON-158):** `treatments` es una lista por paciente: procedimiento, pieza dental FDI opcional (11–48 permanentes, 51–85 temporales, validada en API y base), notas, fecha estimada, consulta en que se propuso (opcional) y consulta en que se realizó. Hay cinco estados, con la matriz `TREATMENT_TRANSITIONS` en `models/treatment.py` (espejo en `components/patients/treatmentStatus.ts`): Propuesto → Aceptado → En curso → Completado, y Cancelado desde cualquiera abierto; Aceptado puede pasar directo a Completado. Completado y Cancelado son finales y bloquean la edición. Completar exige una consulta vigente del mismo paciente (también como restricción en la base) y cancelar exige motivo. Cada cambio queda en `treatment_status_changes` con autor y fecha. Cualquier doctor o admin de la clínica edita y cambia estados. Los cambios bloquean la fila (`SELECT ... FOR UPDATE` solo sobre `treatments`), así que de dos cierres simultáneos pasa uno y el otro recibe `409`. No hay borrado.

## Sesión y tokens

**Flujo:** `POST /auth/login` → JWT (expira en `ACCESS_TOKEN_EXPIRE_MINUTES`, 60 por defecto; con «Recuérdame», `REMEMBER_ME_EXPIRE_DAYS`, 7 por defecto) → `GET /auth/me` carga usuario y clínica. Al recargar, la app muestra un cargador mientras verifica el token con `/auth/me`; si responde `401`, limpia la sesión. Cualquier `401` posterior (token expirado o usuario desactivado) cierra la sesión, avisa al usuario y redirige al login recordando la ruta; un cierre voluntario no la recuerda. Al cerrar sesión se vacía la caché de React Query. Ningún error de login se imprime en consola (el error de Axios incluye el cuerpo con la contraseña).

**Recuperación y cambio de contraseña (ODON-54):**

- `POST /auth/password-reset/request` responde siempre `202` con el mismo mensaje, exista o no la cuenta. Si es una cuenta activa, crea un token aleatorio (`secrets.token_urlsafe`), guarda solo su hash SHA-256 en `password_reset_tokens` y envía el enlace `FRONTEND_URL/reset-password?token=…` en segundo plano. El enlace vence en `PASSWORD_RESET_EXPIRE_MINUTES` (30) y solo vale el último solicitado. Hay un máximo de `PASSWORD_RESET_MAX_PER_HOUR` (3) solicitudes por cuenta: las que lo superan se ignoran en silencio.
- `POST /auth/password-reset/confirm` acepta el token una sola vez (con bloqueo de fila) y responde `400` con el mismo mensaje si es desconocido, usado, vencido o de un usuario inactivo. El frontend quita el token de la barra de direcciones al abrir la página.
- `POST /auth/change-password` (cualquier rol) pide la contraseña actual, rechaza repetirla y devuelve un token nuevo que se guarda en el mismo almacenamiento («Recuérdame» se conserva).
- **Cierre de sesiones:** cambiar o restablecer la contraseña (también por administración en `PATCH /users/{id}`) fija `users.password_changed_at`, y `get_current_user` rechaza con `401` los JWT cuyo `iat` sea anterior. El `iat` lleva fracción de segundo para que no sobreviva un token emitido en el mismo segundo. Es una revocación parcial: el logout sigue sin revocar el token.
- **Correo:** `app/services/email_service.py` envía por SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`). Sin `SMTP_HOST`, el correo se escribe en el log `odontonet.email`, solo para desarrollo. Un fallo de SMTP se registra sin el cuerpo y no cambia la respuesta.

**Evaluación de almacenamiento y refresh (ODON-52):**

| Opción | Ventajas | Riesgos / costo |
| --- | --- | --- |
| A. JWT en `localStorage`, expiración corta, sin refresh (actual) | Simple; sin CSRF | Un XSS podría leer el token; el usuario reingresa cada 60 min |
| B. JWT en cookie `httpOnly` + `Secure` + `SameSite` | El script no puede leer el token | Requiere protección CSRF y cambios de CORS/backend |
| C. Access token en memoria + refresh token rotativo en cookie `httpOnly` | Mejor equilibrio de seguridad y experiencia; permite revocar sesiones | Mayor complejidad: rotación, tabla de sesiones, revocación |

**Recuérdame (ODON-255):** sin marcar, el token corto se guarda en `sessionStorage` y se pierde al cerrar el navegador (una pestaña nueva pide iniciar sesión). Marcado, el token largo se guarda en `localStorage`. Un token largo amplía la ventana de uso si se roba, pero sigue sin funcionar si el usuario se desactiva; la migración a **C** (ODON-230) lo sustituye por un refresh token revocable.

**Decisión:** mantener **A** durante el MVP y el desarrollo, con estas mitigaciones: React escapa el contenido por defecto, no se usa `dangerouslySetInnerHTML`, se auditan dependencias, la expiración es corta y un usuario desactivado pierde el acceso de inmediato. **Antes de producción** (CAL06 / ODON-230) migrar a **C**, agregar Content-Security-Policy y revocación del lado del servidor. Hoy el logout borra el token en el navegador, pero un token copiado sigue siendo válido hasta que expira.

## Contrato de la API

- Documentación interactiva en `/docs` y especificación en `/openapi.json`. Todas las respuestas exitosas tienen un esquema Pydantic; una prueba lo verifica.
- `/health` comprueba la API y la conexión con PostgreSQL (`503` si la base no responde).
- **Formato único de errores** (`backend/app/core/errors.py`): toda respuesta de error es `{"detail": "<mensaje en español>"}`. Los errores de validación (`422`) agregan `errors: [{"field", "message"}]`. Un error de negocio puede agregar datos para la interfaz sin sustituir a `detail`: el `409` por cruce de citas incluye `conflict` (la cita con la que choca, con horas ISO que el navegador muestra en su hora local). Los `500` nunca exponen trazas.
- **Listados paginados** (por ahora `GET /patients/`, ODON-126): responden `{"items", "total", "page", "page_size"}` con `page` desde 1 y `page_size` de 1 a 100 (20 por defecto). Búsqueda y filtros se resuelven en el backend, siempre dentro de la clínica del token. La búsqueda (`q`) cubre nombre y apellidos en cualquier orden, correo y, si el término solo tiene dígitos y separadores (basta un dígito), el teléfono comparado por dígitos. Ignora tildes y mayúsculas con `translate`/`lower` (sin la extensión `unaccent`). El orden usa `COLLATE "C"` sobre el texto normalizado, con la «ñ» después de la «n», así que no depende de la collation de la base.
- Códigos: `401` sin sesión válida (con `WWW-Authenticate: Bearer`), `403` sin permiso por rol, `404` recurso inexistente o de otra clínica, `409` conflicto (duplicado), `422` datos inválidos.

## Limitaciones conocidas

- No existe todavía el alta segura de la primera clínica y su administrador (ODON-74); en desarrollo se usa `seed_dev.py`.
- Faltan edición y desactivación de usuarios (ODON-86, ODON-94) y la navegación por rol en el frontend (ODON-70).
- Token en el almacenamiento del navegador; el servidor solo revoca sesiones al desactivar un usuario o cambiar su contraseña, no en el logout (ver "Sesión y tokens").
- Sin auditoría de acciones clínicas, respaldos verificados ni endurecimiento para producción (épica CAL).
- No hay mecanismo de importación validada de datos de clínicas existentes.

Estas limitaciones son **bloqueantes para un despliegue con datos reales**.

## Evolución prevista

- CRUD completo de pacientes y personal.
- Agenda compartida por clínica, expedientes y periodontograma manual.
- Gestión privada de imágenes clínicas.
- Auditoría, respaldos y despliegue.
- Integración futura con microservicio IA y revisión humana de resultados.

Consulta [Estado del proyecto](PROJECT_STATUS.md) para las prioridades y tickets actuales.
