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

- `src/pages/`: Login, Dashboard y Patients.
- `src/routes/`: navegación y protección básica por presencia de token.
- `src/context/AuthContext.tsx`: login, logout y token en almacenamiento local; **no** implementa todavía recuperación de sesión con `/auth/me`.
- `src/services/`: cliente Axios, servicios de autenticación, pacientes y doctores.
- `src/components/basic/`: componentes visuales reutilizables; `src/components/patients/`: formulario específico del dominio.
- `src/types/`: contratos TypeScript mantenidos manualmente.

### Backend

- `app/main.py`: instancia FastAPI, routers y CORS para `http://localhost:5173`.
- `app/api/`: rutas `/auth`, `/patients`, `/doctors`.
- `app/auth/`: hash de contraseñas, emisión/validación JWT y dependencia de usuario actual.
- `app/models/`: Clinic, User, Doctor y Patient.
- `app/schemas/`: modelos de entrada/salida Pydantic.
- `app/database/`: motor SQLAlchemy, sesiones y dependencia de sesión.
- `alembic/`: control de cambios del esquema; no usar `Base.metadata.create_all` para evolucionar la base.

## Relaciones del modelo

```text
Clinic 1 ── * User
Clinic 1 ── * Doctor
Clinic 1 ── * Patient
User   1 ── 0..1 Doctor
Doctor 1 ── * Patient (asignación opcional del paciente)
```

`Patient.doctor_id` identifica al doctor asignado para organización y filtros. **No define propiedad exclusiva del paciente.** Los profesionales autorizados de la misma clínica deben poder acceder a sus pacientes conforme a permisos.

## Decisiones arquitectónicas

1. **Aislamiento por clínica:** cada recurso clínico deberá estar asociado a una clínica y todas las operaciones deberán limitarse por el `clinic_id` obtenido de la sesión validada en el servidor. No confiar en un `clinic_id` suministrado por el navegador.
2. **Roles:** `admin`, `doctor`, `receptionist` existen como valores de datos; la autorización granular aún está pendiente.
3. **Autenticación:** el backend ofrece `POST /auth/login` y `GET /auth/me`; el frontend conserva el JWT en `localStorage` de manera temporal. Revisar la estrategia de sesión y protección contra XSS antes de producción.
4. **Migraciones:** Alembic es la fuente de verdad para el esquema; la revisión incluida en el repositorio es `e7aac1fc989e` (`initial_schema`).
5. **Separación de IA:** no acoplar PyTorch/OpenCV al backend clínico; definir posteriormente contratos versionados y controles de acceso.
6. **Datos clínicos:** almacenamiento de imágenes, auditoría de accesos y políticas de retención siguen pendientes.

## Contrato de la API

- Documentación interactiva en `/docs` y especificación en `/openapi.json`. Todas las respuestas exitosas tienen un esquema Pydantic; una prueba lo verifica.
- `/health` comprueba la API y la conexión con PostgreSQL (`503` si la base no responde).
- **Formato único de errores** (`backend/app/core/errors.py`): toda respuesta de error es `{"detail": "<mensaje en español>"}`. Los errores de validación (`422`) agregan `errors: [{"field", "message"}]`. Los `500` nunca exponen trazas.
- Códigos: `401` sin sesión válida (con `WWW-Authenticate: Bearer`), `403` sin permiso por rol, `404` recurso inexistente o de otra clínica, `409` conflicto (duplicado), `422` datos inválidos.

## Limitaciones de seguridad conocidas

- Las rutas actuales de pacientes y doctores no requieren `get_current_user` ni aplican filtro por clínica.
- `POST /auth/register` solo lo usa un `admin` y crea el usuario en su propia clínica. Faltan la edición y desactivación de usuarios (ODON-86, ODON-94).
- `/patients/` y `/doctors/` exigen JWT y filtran por la clínica del usuario (ODON-62). Los permisos por rol están en [`PERMISSIONS.md`](PERMISSIONS.md) (ODON-66).
- La existencia de JWT no equivale a un sistema de permisos completo.
- No se ha implementado aún un mecanismo de incorporación de clínicas ni importación validada de bases de datos externas.

Estas limitaciones son **bloqueantes para un despliegue con datos reales** y deberán resolverse en las historias de seguridad, autenticación y multiclínica de Jira.

## Evolución prevista

- Autenticación y autorización por clínica y rol.
- CRUD completo de pacientes y personal.
- Agenda compartida por clínica, expedientes y periodontograma manual.
- Gestión privada de imágenes clínicas.
- Auditoría, pruebas, respaldos y despliegue.
- Integración futura con microservicio IA y revisión humana de resultados.

Consulta [Estado del proyecto](PROJECT_STATUS.md) para las prioridades y tickets actuales.
