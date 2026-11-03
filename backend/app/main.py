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
from app.api.doctor_routes import router as doctor_router
from app.api.medical_history_routes import router as medical_history_router
from app.api.patient_routes import router as patient_router
from app.api.user_routes import router as user_router
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

# Orígenes permitidos separados por coma (CORS_ORIGINS en backend/.env).
origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
