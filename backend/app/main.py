import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.appointment_routes import router as appointment_router
from app.api.auth_routes import router as auth_router
from app.api.clinic_routes import router as clinic_router
from app.api.clinical_visit_routes import router as clinical_visit_router
from app.api.dashboard_routes import router as dashboard_router
from app.api.doctor_routes import router as doctor_router
from app.api.medical_history_routes import router as medical_history_router
from app.api.patient_routes import router as patient_router
from app.api.periodontal_routes import router as periodontal_router
from app.api.report_routes import router as report_router
from app.api.timeline_routes import router as timeline_router
from app.api.patient_image_routes import router as patient_image_router
from app.api.photo_consent_routes import router as photo_consent_router
from app.api.treatment_routes import router as treatment_router
from app.api.user_routes import router as user_router
from app.core.allowed_hosts import AllowedHostsMiddleware, parse_allowed_hosts
from app.core.errors import register_exception_handlers
from app.database.dependencies import get_db

# Loggers propios (odontonet.api, odontonet.audit): nivel INFO a la consola,
# donde uvicorn ya escribe. La auditoría persistente se diseña en ODON-222.
_app_logger = logging.getLogger("odontonet")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)

app = FastAPI(
    title="OdontoNet API",
    version="0.1.0",
    description=(
        "API de gestión clínica odontológica. Todas las rutas, salvo login y "
        "health, requieren JWT y se limitan a la clínica del usuario."
    ),
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(clinic_router)
app.include_router(patient_router)
app.include_router(doctor_router)
app.include_router(user_router)
app.include_router(appointment_router)
app.include_router(medical_history_router)
app.include_router(clinical_visit_router)
app.include_router(treatment_router)
app.include_router(timeline_router)
app.include_router(patient_image_router)
app.include_router(photo_consent_router)
app.include_router(periodontal_router)
app.include_router(dashboard_router)
app.include_router(report_router)

def cors_origins(raw: str) -> list[str]:
    """Orígenes permitidos separados por coma (CORS_ORIGINS en backend/.env).

    Con credenciales, un comodín permitiría que cualquier sitio use la sesión
    del usuario (ODON-230): se rechaza al arrancar."""
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if any("*" in origin for origin in origins):
        raise RuntimeError("CORS_ORIGINS no admite '*': lista los orígenes exactos del frontend.")
    return origins


origins = cors_origins(os.getenv("CORS_ORIGINS", "http://localhost:5173"))

# Solo se atienden peticiones dirigidas a los hosts de ALLOWED_HOSTS (ODON-263).
allowed_hosts = parse_allowed_hosts(os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1"))
app.add_middleware(AllowedHostsMiddleware, allowed_hosts=allowed_hosts)

# Cabeceras de seguridad en todas las respuestas (ODON-230). La documentación
# interactiva (/docs, /redoc) carga recursos externos y no lleva CSP estricta.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if not request.url.path.startswith(_DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", API_CSP)
        # Respuestas con datos de pacientes: que ningún navegador ni proxy las guarde.
        response.headers.setdefault("Cache-Control", "no-store")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # El frontend lee el nombre del archivo de las descargas (reporte PDF, ODON-198).
    expose_headers=["Content-Disposition"],
)


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str


@app.get("/", response_model=MessageResponse, tags=["Health"])
def root():
    return {"message": "OdontoNet API running"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health(db: Session = Depends(get_db)):
    """Verifica que la API responde y que la base de datos es accesible."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return {"status": "ok", "database": "ok"}
