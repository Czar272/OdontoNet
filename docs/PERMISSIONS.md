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
| `GET /clinic` (datos de la propia clínica) | ✅ | ✅ | ✅ |
| `PATCH /clinic` (editar la propia clínica) | ✅ | ⛔ | ⛔ |
| `POST /auth/register` (crear usuario en su clínica; equivale a `POST /users/`) | ✅ | ⛔ | ⛔ |
| `GET /users/`, `GET /users/{id}` (personal de su clínica) | ✅ | ⛔ | ⛔ |
| `POST /users/`, `PATCH /users/{id}` (alta y edición) | ✅ | ⛔ | ⛔ |
| `POST /users/{id}/deactivate`, `POST /users/{id}/activate` | ✅ | ⛔ | ⛔ |
| `GET /patients/`, `GET /patients/{id}` | ✅ | ✅ | ✅ |
| `POST /patients/` | ✅ | ✅ | ✅ |
| `PATCH /patients/{id}` (editar datos y reasignar doctor) | ✅ | ✅ | ✅ |
| `GET /patients/?archived=true` (listar archivados; por defecto solo activos) | ✅ | ✅ | ✅ |
| `POST /patients/{id}/archive`, `POST /patients/{id}/reactivate` | ✅ | ✅ | ✅ |
| `GET /doctors/` (filtro `?active=true/false`), `GET /doctors/{id}` | ✅ | ✅ | ✅ |
| `POST /doctors/` (crear perfil de doctor), `PATCH /doctors/{id}` (editar perfil) | ✅ | ⛔ | ⛔ |

Verificado por `backend/tests/test_rbac.py`, `backend/tests/test_users.py`, `backend/tests/test_user_deactivation.py` y `backend/tests/test_patient_archive.py`.

### Reglas de gestión de usuarios (ODON-86)

- La clínica del usuario creado es siempre la del administrador; un `clinic_id` enviado se ignora y no se puede cambiar al editar.
- El correo es único en todo el sistema (identifica el inicio de sesión): `409` si ya existe.
- Un administrador no puede cambiar su propio rol, para que la clínica no se quede sin administración.
- El rol de un usuario con perfil de doctor no se puede cambiar mientras exista el perfil (`409`).
- La contraseña nunca se devuelve; enviarla en `PATCH` la restablece.
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
- El correo de un paciente archivado sigue reservado en su clínica: crear otro paciente con ese correo responde `409`.

## Módulos futuros (decidido el 2026-10-31)

Se implementarán con esta matriz cuando se desarrolle cada módulo.

| Recurso | admin | doctor | receptionist |
| --- | :---: | :---: | :---: |
| Citas y agenda | ✅ | ✅ | ✅ |
| Disponibilidad de doctores | ✅ | ✅ la propia | ✅ |
| Expediente clínico (antecedentes, notas, tratamientos) | ✅ | ✅ | ⛔ |
| Imágenes clínicas | ✅ | ✅ | ⛔ |
| Periodontograma | ✅ | ✅ | ⛔ |
| Reportes operativos | ✅ | ✅ | ✅ sin datos clínicos |

**Decisiones:**

- **El administrador tiene acceso clínico.** En clínicas pequeñas el administrador suele ser también odontólogo. Se mantiene un solo rol por usuario.
- **Recepción no accede a datos clínicos:** ni expediente, ni imágenes, ni periodontograma. Gestiona datos demográficos y agenda.

## Modelo de roles objetivo (aprobado el 2026-11-01)

Recoge la visión del desarrollador sin cambiar lo implementado. Cada fila se aplica cuando llegue su módulo.

| Nivel | Rol (clave) | Alcance | Cuándo |
| --- | --- | --- | --- |
| Plataforma | `superadmin` (nuevo) | Crear y administrar clínicas, soporte. No pertenece a una clínica; actúa sobre una clínica de forma explícita y auditada. Un solo usuario por ahora. | Con ODON-74 (alta de clínicas) |
| Clínica | `admin` («Administración») | Toda su clínica: personal, configuración, pacientes y agenda. Puede tener perfil de doctor. | Implementado |
| Clínica | `doctor` | Atención clínica completa. Edita su propio perfil; no gestiona usuarios ni roles y no puede desactivarse. | Implementado; falta «Mi perfil» |
| Clínica | `receptionist` («Recepción») | Pacientes (datos generales, doctor asignado), agenda e información médica básica. Sin periodontograma, diagnósticos ni notas clínicas. | Ajustar con el expediente (ODON-7) |
| Externo | `patient` | Solo lectura de su propia información, con autenticación separada (portal). | Después del MVP |

Pautas para no rehacer trabajo:

- La etiqueta visible sigue siendo «Recepción» (decisión del desarrollador); si algún día cambia, solo cambia `ROLE_LABELS`, no la clave guardada.
- `superadmin` no será un `admin` con permisos extra: su `clinic_id` no aplica, y cada acción entre clínicas indicará la clínica destino y quedará auditada (ODON-222). Así el aislamiento por clínica sigue siendo la regla para todos los demás roles.
- Los permisos finos (por ejemplo, qué campos médicos edita el asistente) se declaran por módulo en esta matriz y en `frontend/src/auth/permissions.ts`.
