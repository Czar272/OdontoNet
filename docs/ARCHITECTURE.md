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
- `src/routes/`: router, ruta protegida por presencia de token y ruta comodín.
- `src/layouts/`: barra lateral con navegación activa y cierre de sesión (limpia token y caché).
- `src/context/AuthContext.tsx`: login, logout y token en `localStorage`. **No** restaura todavía usuario/clínica con `/auth/me` ni reacciona a un `401` (AUT03/AUT04).
- `src/services/`: cliente Axios (`VITE_API_URL`), servicios por recurso y `apiError.ts` para mostrar el `detail` de la API.
- `src/components/basic/`: Button, Input, Select, Modal, Table, Card, PageHeader, LoadingSpinner (accesibles); `src/components/patients/`: formulario del dominio.
- `src/types/`: contratos TypeScript mantenidos manualmente.

### Backend

- `app/main.py`: instancia FastAPI, routers, manejadores de error, CORS (`CORS_ORIGINS`) y `/health`.
- `app/api/`: rutas `/auth`, `/patients`, `/doctors`.
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
User   1 ── 0..1 Doctor
Doctor 1 ── * Patient (asignación opcional del paciente)
```

`Patient.doctor_id` identifica al doctor asignado para organización y filtros. **No define propiedad exclusiva del paciente:** los usuarios autorizados de la misma clínica acceden a sus pacientes según su rol. El correo del paciente es único dentro de cada clínica.

## Decisiones arquitectónicas

1. **Aislamiento por clínica:** todo recurso clínico pertenece a una clínica y toda operación se limita por el `clinic_id` del usuario autenticado (`get_current_clinic_id`). Un `clinic_id` enviado por el navegador se ignora. Un recurso de otra clínica responde `404`.
2. **Roles:** `admin`, `doctor` y `receptionist`, un rol por usuario, aplicados en el backend con `require_roles` y leídos de la base en cada petición. Matriz y decisiones en [`PERMISSIONS.md`](PERMISSIONS.md).
3. **Autenticación:** `POST /auth/login` emite un JWT con expiración configurable; `GET /auth/me` devuelve usuario y clínica. Usuarios inactivos no inician sesión y sus tokens dejan de valer. El frontend guarda el JWT en `localStorage` de forma temporal; revisar la estrategia frente a XSS antes de producción.
4. **Migraciones:** Alembic es la fuente de verdad del esquema. Cadena lineal: `e7aac1fc989e` (esquema inicial) → `4c1d2e8f9a10` (correo único por clínica e índices `clinic_id`). Checklist de revisión en `DEVELOPMENT.md`.
5. **Pruebas:** pytest contra una base PostgreSQL `*_test` que aplica todas las migraciones; incluyen aislamiento entre dos clínicas, matriz de roles, contrato de la API y seed.
6. **Separación de IA:** no acoplar PyTorch/OpenCV al backend clínico; definir posteriormente contratos versionados y controles de acceso.
7. **Datos clínicos:** almacenamiento de imágenes, auditoría de accesos y políticas de retención siguen pendientes.

## Contrato de la API

- Documentación interactiva en `/docs` y especificación en `/openapi.json`. Todas las respuestas exitosas tienen un esquema Pydantic; una prueba lo verifica.
- `/health` comprueba la API y la conexión con PostgreSQL (`503` si la base no responde).
- **Formato único de errores** (`backend/app/core/errors.py`): toda respuesta de error es `{"detail": "<mensaje en español>"}`. Los errores de validación (`422`) agregan `errors: [{"field", "message"}]`. Los `500` nunca exponen trazas.
- Códigos: `401` sin sesión válida (con `WWW-Authenticate: Bearer`), `403` sin permiso por rol, `404` recurso inexistente o de otra clínica, `409` conflicto (duplicado), `422` datos inválidos.

## Limitaciones conocidas

- No existe todavía el alta segura de la primera clínica y su administrador (ODON-74); en desarrollo se usa `seed_dev.py`.
- Faltan edición y desactivación de usuarios (ODON-86, ODON-94) y la navegación por rol en el frontend (ODON-70).
- El frontend no restaura la sesión con `/auth/me` ni cierra la sesión ante un `401` (ODON-46, ODON-50).
- Sin auditoría de acciones clínicas, respaldos verificados ni endurecimiento para producción (épica CAL).
- No hay mecanismo de importación validada de datos de clínicas existentes.

Estas limitaciones son **bloqueantes para un despliegue con datos reales**.

## Evolución prevista

- Sesión completa en frontend y navegación por rol.
- CRUD completo de pacientes y personal.
- Agenda compartida por clínica, expedientes y periodontograma manual.
- Gestión privada de imágenes clínicas.
- Auditoría, respaldos y despliegue.
- Integración futura con microservicio IA y revisión humana de resultados.

Consulta [Estado del proyecto](PROJECT_STATUS.md) para las prioridades y tickets actuales.
