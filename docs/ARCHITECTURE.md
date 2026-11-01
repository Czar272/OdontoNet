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

- `src/pages/`: inicio de sesión, inicio (dashboard) y pacientes. Interfaz en español.
- `src/routes/`: router, ruta protegida (espera la verificación de sesión y recuerda la ruta solicitada), `RequirePermission` (página "Acceso denegado" si el rol no tiene permiso) y ruta comodín.
- `src/auth/permissions.ts`, `src/config/navigation.ts`, `src/hooks/usePermission.ts`: permisos por rol reflejados de `PERMISSIONS.md`; el menú y las acciones se muestran según el rol. El backend sigue siendo la autoridad.
- `src/layouts/`: barra lateral con clínica, usuario, rol, navegación activa y cierre de sesión.
- `src/context/AuthContext.tsx`: sesión con estados `loading` / `authenticated` / `unauthenticated`; restaura usuario y clínica con `/auth/me` al cargar; login, logout y cierre automático ante un `401`.
- `src/services/`: cliente Axios (`VITE_API_URL`) con interceptor de `401`, `session.ts` (token), servicios por recurso y `apiError.ts` para mostrar el `detail` de la API.
- `src/components/basic/`: Button, Input, Select, Modal, Table, Card, PageHeader, LoadingSpinner (accesibles); `src/components/<dominio>/`: formularios de pacientes y usuarios.
- `src/types/`: contratos TypeScript mantenidos manualmente.

### Backend

- `app/main.py`: instancia FastAPI, routers, manejadores de error, CORS (`CORS_ORIGINS`) y `/health`.
- `app/api/`: rutas `/auth`, `/clinic`, `/patients`, `/doctors`, `/users`. `/clinic` no recibe id: siempre opera sobre la clínica de la sesión.
- `app/services/`: reglas de negocio compartidas entre rutas (`user_service.py`: alta y edición de usuarios).
- `app/auth/`: hash de contraseñas, JWT, usuario actual (`get_current_user`), clínica actual (`get_current_clinic_id`) y roles (`permissions.py`, `require_roles`).
- `app/core/errors.py`: formato único de errores.
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
Doctor 1 ── * Patient (asignación opcional del paciente)
```

`Patient.doctor_id` identifica al doctor asignado para organización y filtros. **No define propiedad exclusiva del paciente:** los usuarios autorizados de la misma clínica acceden a sus pacientes según su rol. El correo del paciente es único dentro de cada clínica.

**Integridad User–Doctor (ODON-78):** `uq_doctors_user_id` impide un segundo perfil para el mismo usuario y `fk_doctors_user_clinic` (`doctors(user_id, clinic_id)` → `users(id, clinic_id)`) impide un perfil en otra clínica que su usuario. Usuarios y doctores no se borran: un usuario con perfil o un doctor con pacientes no se puede eliminar (las FK lo bloquean y el ORM usa `passive_deletes`); el acceso se retira desactivando (ODON-94).

## Decisiones arquitectónicas

1. **Aislamiento por clínica:** todo recurso clínico pertenece a una clínica y toda operación se limita por el `clinic_id` del usuario autenticado (`get_current_clinic_id`). Un `clinic_id` enviado por el navegador se ignora. Un recurso de otra clínica responde `404`.
2. **Roles:** `admin`, `doctor` y `receptionist`, un rol por usuario, aplicados en el backend con `require_roles` y leídos de la base en cada petición. Matriz y decisiones en [`PERMISSIONS.md`](PERMISSIONS.md).
3. **Autenticación:** `POST /auth/login` emite un JWT con expiración configurable; `GET /auth/me` devuelve usuario y clínica. Usuarios inactivos no inician sesión y sus tokens dejan de valer. El frontend guarda el JWT en `sessionStorage` (o en `localStorage` con «Recuérdame») de forma temporal; revisar la estrategia frente a XSS antes de producción.
4. **Migraciones:** Alembic es la fuente de verdad del esquema. Cadena lineal: `e7aac1fc989e` (esquema inicial) → `4c1d2e8f9a10` (correo único por clínica e índices `clinic_id`) → `7b3e9d2c5a61` (User–Doctor uno a uno y misma clínica; se detiene si hay datos que lo violan). Checklist de revisión en `DEVELOPMENT.md`.
5. **Pruebas:** pytest contra una base PostgreSQL `*_test` que aplica todas las migraciones; incluyen aislamiento entre dos clínicas, matriz de roles, contrato de la API y seed.
6. **Separación de IA:** no acoplar PyTorch/OpenCV al backend clínico; definir posteriormente contratos versionados y controles de acceso.
7. **Datos clínicos:** almacenamiento de imágenes, auditoría de accesos y políticas de retención siguen pendientes.

## Sesión y tokens

**Flujo:** `POST /auth/login` → JWT (expira en `ACCESS_TOKEN_EXPIRE_MINUTES`, 60 por defecto; con «Recuérdame», `REMEMBER_ME_EXPIRE_DAYS`, 7 por defecto) → `GET /auth/me` carga usuario y clínica. Al recargar, la app muestra un cargador mientras verifica el token con `/auth/me`; si responde `401`, limpia la sesión. Cualquier `401` posterior (token expirado o usuario desactivado) cierra la sesión, avisa al usuario y redirige al login recordando la ruta; un cierre voluntario no la recuerda. Al cerrar sesión se vacía la caché de React Query. Ningún error de login se imprime en consola (el error de Axios incluye el cuerpo con la contraseña).

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
- **Formato único de errores** (`backend/app/core/errors.py`): toda respuesta de error es `{"detail": "<mensaje en español>"}`. Los errores de validación (`422`) agregan `errors: [{"field", "message"}]`. Los `500` nunca exponen trazas.
- Códigos: `401` sin sesión válida (con `WWW-Authenticate: Bearer`), `403` sin permiso por rol, `404` recurso inexistente o de otra clínica, `409` conflicto (duplicado), `422` datos inválidos.

## Limitaciones conocidas

- No existe todavía el alta segura de la primera clínica y su administrador (ODON-74); en desarrollo se usa `seed_dev.py`.
- Faltan edición y desactivación de usuarios (ODON-86, ODON-94) y la navegación por rol en el frontend (ODON-70).
- Token en el almacenamiento del navegador y sin revocación del lado del servidor hasta producción (ver "Sesión y tokens").
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
