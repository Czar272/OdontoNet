# Matriz de permisos (RBAC) — OdontoNet

> Fuente de verdad de qué puede hacer cada rol. Toda regla se aplica en el backend
> (`require_roles` en `backend/app/auth/permissions.py`); ocultar un botón en el
> frontend no es un control de acceso.
>
> El frontend refleja esta matriz en `frontend/src/auth/permissions.ts` para adaptar
> el menú (`config/navigation.ts`), las rutas (`RequirePermission`) y las acciones
> (`usePermission`). Al cambiar un permiso, actualiza ambos lados y sus pruebas.

## Principios

1. **Aislamiento primero:** todo acceso se limita a la clínica del usuario autenticado (ODON-62). Los roles deciden *qué* se puede hacer dentro de esa clínica.
2. **Rol desde la base de datos:** se lee del usuario en cada petición, no del token; un cambio de rol o una desactivación tienen efecto inmediato.
3. **Denegar por defecto:** un rol desconocido no tiene permisos. Las respuestas son `401` sin sesión válida y `403` con sesión pero sin permiso.
4. **Los doctores comparten la información de su clínica:** la asignación doctor–paciente organiza el trabajo, no restringe el acceso.

## Roles

| Rol | Clave | Propósito |
| --- | --- | --- |
| Administrador | `admin` | Gestiona usuarios, doctores y configuración de su clínica. |
| Doctor | `doctor` | Atención clínica: pacientes, expediente, imágenes y periodontograma. |
| Recepción | `receptionist` | Tareas administrativas: registro de pacientes y agenda. |

## Endpoints implementados

✅ permitido · ⛔ 403

| Endpoint | admin | doctor | receptionist |
| --- | :---: | :---: | :---: |
| `POST /auth/login` | público | público | público |
| `GET /auth/me` | ✅ | ✅ | ✅ |
| `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm` (recuperación por correo) | público | público | público |
| `POST /auth/change-password` (contraseña propia) | ✅ | ✅ | ✅ |
| `GET /clinic` (datos de la propia clínica) | ✅ | ✅ | ✅ |
| `PATCH /clinic` (editar la propia clínica) | ✅ | ⛔ | ⛔ |
| `POST /auth/register` (crear usuario en su clínica; equivale a `POST /users/`) | ✅ | ⛔ | ⛔ |
| `GET /users/`, `GET /users/{id}` (personal de su clínica) | ✅ | ⛔ | ⛔ |
| `POST /users/`, `PATCH /users/{id}` (alta y edición) | ✅ | ⛔ | ⛔ |
| `POST /users/{id}/deactivate`, `POST /users/{id}/activate` | ✅ | ⛔ | ⛔ |
| `GET /patients/`, `GET /patients/{id}` | ✅ | ✅ | ✅ |
| `POST /patients/` | ✅ | ✅ | ✅ |
| `PATCH /patients/{id}` (editar datos y reasignar doctor) | ✅ | ✅ | ✅ |
| `GET /patients/` con `archived`, `q`, `doctor_id`, `page`, `page_size` (listado paginado; por defecto activos) | ✅ | ✅ | ✅ |
| `POST /patients/{id}/archive`, `POST /patients/{id}/reactivate` | ✅ | ✅ | ✅ |
| `GET /appointments/` (rango `start`–`end` o `patient_id`; filtros `doctor_id`, `status`), `GET /appointments/{id}` | ✅ | ✅ | ✅ |
| `POST /appointments/`, `PATCH /appointments/{id}` (agendar y reprogramar) | ✅ | ✅ | ✅ |
| `POST /appointments/{id}/status` (confirmar, cancelar, atendida, no asistió, reactivar), `GET /appointments/{id}/history` | ✅ | ✅ | ✅ |
| `GET /doctors/` (filtro `?active=true/false`), `GET /doctors/{id}` | ✅ | ✅ | ✅ |
| `POST /doctors/` (crear perfil de doctor), `PATCH /doctors/{id}` (editar perfil) | ✅ | ⛔ | ⛔ |
| `GET /doctors/availability`, `GET /doctors/{id}/availability` (horarios) | ✅ | ✅ | ✅ |
| `PUT /doctors/{id}/availability` (reemplaza el horario semanal) | ✅ | ✅ solo el propio | ✅ |
| `GET /patients/{id}/medical-history`, `.../versions`, `.../versions/{n}` (historia médica vigente y versiones) | ✅ | ✅ | ✅ |
| `POST /patients/{id}/medical-history` (guardar una versión nueva) | ✅ | ✅ | ⛔ |
| `GET /patients/{id}/visits`, `.../visits/{v}`, `.../visits/{v}/revisions` (consultas e historial de cambios) | ✅ | ✅ | ⛔ |
| `POST /patients/{id}/visits` (registrar consulta) | ✅ | ✅ | ⛔ |
| `PUT /patients/{id}/visits/{v}`, `POST .../visits/{v}/void` (editar o anular) | ✅ cualquiera | ✅ solo las que registró | ⛔ |
| `GET /patients/{id}/treatments`, `.../treatments/{t}`, `.../treatments/{t}/history` (plan de tratamiento) | ✅ | ✅ | ⛔ |
| `POST /patients/{id}/treatments`, `PATCH .../treatments/{t}`, `POST .../treatments/{t}/status` (registrar, editar y cambiar estado) | ✅ | ✅ cualquiera | ⛔ |
| `GET /patients/{id}/timeline` (historial cronológico; filtros `types`, `cursor`, `limit`) | ✅ | ✅ | ⛔ |

Verificado por `backend/tests/test_rbac.py`, `backend/tests/test_password_reset.py`, `backend/tests/test_users.py`, `backend/tests/test_user_deactivation.py`, `backend/tests/test_patient_archive.py`, `backend/tests/test_appointment_api.py`, `backend/tests/test_doctor_availability.py`, `backend/tests/test_medical_history.py`, `backend/tests/test_clinical_visits.py`, `backend/tests/test_treatments.py` y `backend/tests/test_timeline.py`.

### Reglas de gestión de usuarios (ODON-86)

- La clínica del usuario creado es siempre la del administrador; un `clinic_id` enviado se ignora y no se puede cambiar al editar.
- El correo es único en todo el sistema (identifica el inicio de sesión): `409` si ya existe.
- Un administrador no puede cambiar su propio rol, para que la clínica no se quede sin administración.
- El rol de un usuario con perfil de doctor no se puede cambiar mientras exista el perfil (`409`).
- La contraseña nunca se devuelve; enviarla en `PATCH` la restablece, cierra las sesiones abiertas de ese usuario y anula sus enlaces de recuperación pendientes (ODON-54).
- Un administrador no cambia su propia contraseña con `PATCH /users/{id}` (`409`): usa `POST /auth/change-password`, que pide la contraseña actual.
- Cambiar el correo de un usuario invalida su sesión actual (el token se identifica por correo), así que debe volver a iniciar sesión.

### Desactivación (ODON-94)

- Desactivar no borra nada: el usuario, su perfil de doctor y los pacientes asignados se conservan y siguen visibles.
- Un usuario inactivo no inicia sesión (`401 Credenciales inválidas.`, sin revelar el motivo) y su token deja de funcionar en la siguiente petición (`401`), porque el estado se lee de la base en cada petición.
- Un administrador no puede desactivarse a sí mismo (`409`). Activar y desactivar son idempotentes.
- `is_active` solo cambia con estos endpoints; `PATCH /users/{id}` lo ignora.
- El perfil de doctor (especialidad, colegiado, teléfono) solo se crea para un usuario con rol `doctor` o `admin` de la misma clínica (`422` si no; decisión del 2026-11-01: el administrador que atiende puede tener pacientes asignados) y es único por usuario (`409`). Su estado activo es el del usuario: se cambia en Usuarios (ODON-90).
- Un doctor inactivo sigue en el historial y en `GET /doctors/` sin filtro, pero no se le pueden asignar pacientes nuevos (`422 El doctor seleccionado está inactivo.`, ODON-82). El formulario de pacientes solo ofrece doctores activos.

### Archivo de pacientes (ODON-122)

- Archivar no borra nada: datos, doctor asignado (aunque esté inactivo) e historial se conservan. `archived_at` guarda la fecha; `null` es activo.
- `GET /patients/` devuelve solo activos; `?archived=true` devuelve solo archivados. La ficha `GET /patients/{id}` funciona en ambos estados.
- Un paciente archivado no se edita (`409 El paciente está archivado. Reactívalo para editar sus datos.`); primero se reactiva.
- Archivar y reactivar son idempotentes y quedan en el log `odontonet.audit` (solo ids). Un paciente de otra clínica responde `404`.
- El correo de un paciente archivado sigue reservado en su clínica: crear o editar otro paciente con ese correo responde `409 Ya existe un paciente archivado con ese correo en la clínica. Reactívalo desde la lista de archivados.`

### Citas (ODON-134)

- La clínica de la cita sale del token; el estado inicial es siempre «Programada» y el autor es el usuario de la sesión. `clinic_id`, `status` y `created_by_user_id` enviados se ignoran.
- Paciente y doctor deben ser de la clínica (`422`). El doctor debe estar activo (`422 El doctor seleccionado está inactivo.`). No se agenda a un paciente archivado (`409`).
- El inicio lleva zona horaria, es exacto al minuto y no puede estar en el pasado (`422`). La duración va de 5 a 480 minutos (30 por defecto).
- Ni el doctor ni el paciente pueden tener dos citas activas que se crucen (`409`). El mensaje nombra al doctor («Dra. Ana Morales ya tiene una cita…» o «El paciente ya tiene una cita con Dra. Ana Morales…») y la respuesta incluye `conflict` con la cita que choca; la agenda agrega su horario en hora local. Cancelada y No asistió liberan el horario. La base lo garantiza aunque dos peticiones lleguen a la vez.
- Solo se reprograman citas programadas o confirmadas (`409`). El paciente de una cita no cambia.
- No se borra ninguna cita (no hay `DELETE`): se cancelan.

### Estados de citas (ODON-146)

| Desde \ hacia | Programada | Confirmada | Atendida | No asistió | Cancelada |
| --- | :---: | :---: | :---: | :---: | :---: |
| Programada | — | ✅ antes de terminar | ✅ desde que empieza | ✅ desde que empieza | ✅ antes de terminar |
| Confirmada | ✅ antes de terminar | — | ✅ desde que empieza | ✅ desde que empieza | ✅ antes de terminar |
| Cancelada | ✅ si aún no empieza (reactivar) | ⛔ | ⛔ | ⛔ | — |
| Atendida | ⛔ | ⛔ | — | ✅ (corrección) | ⛔ |
| No asistió | ⛔ | ⛔ | ✅ (corrección) | — | ⛔ |

- Un cambio no permitido responde `409` en español («Una cita atendida no puede pasar a cancelada.», «La cita todavía no empieza…», «La cita ya terminó…»). Repetir el estado actual no cambia nada.
- Reactivar una cancelada vuelve a ocupar el horario: se valida como una cita nueva (inicio futuro, doctor activo, paciente no archivado y sin cruces, `409` con `conflict`).
- Cada cambio queda en `appointment_status_changes`, con estado anterior, nuevo estado, nota opcional (hasta 255 caracteres, sin datos clínicos), usuario y fecha. Las citas creadas desde esta versión registran también su creación. El historial no se edita ni se borra.
- `GET /appointments/` devuelve el teléfono del paciente para que recepción llame a confirmar. La pestaña «Por confirmar» de la Agenda lista las programadas del periodo elegido y permite confirmar o cancelar desde ahí.
- Un paciente con citas próximas pendientes (programadas o confirmadas que aún no terminan) no se archiva (`409 El paciente tiene N citas próximas...`).
- Las horas se muestran en la hora local del navegador (decisión del 2026-11-02).
- En el frontend, `appointments:view` (menú «Agenda» y ruta `/agenda`) y `appointments:manage` (agendar, arrastrar y reprogramar) son para los tres roles.

### Horario de los doctores (ODON-142)

- Cada doctor tiene un horario semanal de bloques por día (por ejemplo, 08:00–12:00 y 14:00–18:00). Las horas son de la zona horaria de la clínica (`clinics.timezone`, por defecto `America/Guatemala`, editable por administración en «Clínica»).
- Administración y recepción editan el horario de cualquier doctor; un doctor solo el suyo (`403 Solo puedes editar tu propio horario.`). Todos lo consultan. El cambio queda en la auditoría (`doctor.availability_updated`).
- Los bloques de un día no se cruzan, son exactos al minuto y la hora de fin es posterior a la de inicio (`422`).
- Agendar o reprogramar fuera del horario responde `409` con `outside_schedule: true` y un mensaje que describe el horario del día («Dra. Ana Morales no atiende en ese horario. Su horario del martes es 08:00–12:00 y 14:00–18:00.»). Si el usuario confirma, el frontend reenvía con `allow_outside_schedule: true` y la cita se guarda (decisión del 2026-11-02: avisar y permitir). El permiso no se guarda en la cita.
- Un doctor sin horario registrado se agenda a cualquier hora (decisión del 2026-11-02). Reactivar una cancelada no revisa el horario.
- En la Agenda, las horas fuera del horario del doctor filtrado (o de todos, sin filtro) aparecen sombreadas, y se avisa qué doctores no tienen horario. Las ausencias puntuales (vacaciones, permisos) quedan para ODON-258 (CIT-ENH02).

## Módulos futuros (decidido el 2026-10-31)

Se implementarán con esta matriz cuando se desarrolle cada módulo.

| Recurso | admin | doctor | receptionist |
| --- | :---: | :---: | :---: |
| Historia médica y odontológica (antecedentes, ODON-150) | ✅ | ✅ | 👁️ solo lectura |
| Consultas clínicas (ODON-154) | ✅ | ✅ (edita o anula solo las propias) | ⛔ |
| Plan de tratamiento (ODON-158) | ✅ | ✅ (cualquier tratamiento; el historial registra quién) | ⛔ |
| Historial cronológico (ODON-162) | ✅ | ✅ | ⛔ (incluye consultas y tratamientos) |
| Imágenes clínicas | ✅ | ✅ | ⛔ |
| Periodontograma | ✅ | ✅ | ⛔ |
| Reportes operativos | ✅ | ✅ | ✅ sin datos clínicos |

**Decisiones:**

- **El administrador tiene acceso clínico.** En clínicas pequeñas el administrador suele ser también odontólogo. Se mantiene un solo rol por usuario.
- **Recepción no accede a datos clínicos:** ni expediente, ni imágenes, ni periodontograma. Gestiona datos demográficos y agenda.
- **Excepción, decidida el 2026-11-02 (ODON-150):** Recepción lee la historia médica y odontológica completa (vigente y versiones anteriores), pero no la edita (`403`). Así ve alergias y condiciones al agendar o recibir al paciente. Las consultas, notas y tratamientos siguen fuera de su alcance.

## Modelo de roles objetivo (aprobado el 2026-11-01)

Recoge la visión del desarrollador sin cambiar lo implementado. Cada fila se aplica cuando llegue su módulo.

| Nivel | Rol (clave) | Alcance | Cuándo |
| --- | --- | --- | --- |
| Plataforma | `superadmin` (nuevo) | Crear y administrar clínicas, soporte. No pertenece a una clínica; actúa sobre una clínica de forma explícita y auditada. Un solo usuario por ahora. | Con ODON-74 (alta de clínicas) |
| Clínica | `admin` («Administración») | Toda su clínica: personal, configuración, pacientes y agenda. Puede tener perfil de doctor. | Implementado |
| Clínica | `doctor` | Atención clínica completa. Edita su propio perfil; no gestiona usuarios ni roles y no puede desactivarse. | Implementado; falta «Mi perfil» |
| Clínica | `receptionist` («Recepción») | Pacientes (datos generales, doctor asignado), agenda y lectura de la historia médica. Sin periodontograma, diagnósticos ni notas clínicas. | Historia médica: ODON-150 |
| Externo | `patient` | Solo lectura de su propia información, con autenticación separada (portal). | Después del MVP |

Pautas para no rehacer trabajo:

- La etiqueta visible sigue siendo «Recepción» (decisión del desarrollador); si algún día cambia, solo cambia `ROLE_LABELS`, no la clave guardada.
- `superadmin` no será un `admin` con permisos extra: su `clinic_id` no aplica, y cada acción entre clínicas indicará la clínica destino y quedará auditada (ODON-222). Así el aislamiento por clínica sigue siendo la regla para todos los demás roles.
- Los permisos finos (por ejemplo, qué campos médicos edita el asistente) se declaran por módulo en esta matriz y en `frontend/src/auth/permissions.ts`.
