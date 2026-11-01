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
| `POST /auth/register` (crear usuario en su clínica) | ✅ | ⛔ | ⛔ |
| `GET /patients/`, `GET /patients/{id}` | ✅ | ✅ | ✅ |
| `POST /patients/` | ✅ | ✅ | ✅ |
| `GET /doctors/`, `GET /doctors/{id}` | ✅ | ✅ | ✅ |
| `POST /doctors/` (crear perfil de doctor) | ✅ | ⛔ | ⛔ |

Verificado por `backend/tests/test_rbac.py`.

## Módulos futuros (decidido el 2026-10-31)

Se implementarán con esta matriz cuando se desarrolle cada módulo.

| Recurso | admin | doctor | receptionist |
| --- | :---: | :---: | :---: |
| Editar / archivar pacientes | ✅ | ✅ | ✅ datos demográficos |
| Citas y agenda | ✅ | ✅ | ✅ |
| Disponibilidad de doctores | ✅ | ✅ la propia | ✅ |
| Expediente clínico (antecedentes, notas, tratamientos) | ✅ | ✅ | ⛔ |
| Imágenes clínicas | ✅ | ✅ | ⛔ |
| Periodontograma | ✅ | ✅ | ⛔ |
| Usuarios, desactivación y configuración de clínica | ✅ | ⛔ | ⛔ |
| Reportes operativos | ✅ | ✅ | ✅ sin datos clínicos |

**Decisiones:**

- **El administrador tiene acceso clínico.** En clínicas pequeñas el administrador suele ser también odontólogo. Se mantiene un solo rol por usuario.
- **Recepción no accede a datos clínicos:** ni expediente, ni imágenes, ni periodontograma. Gestiona datos demográficos y agenda.
