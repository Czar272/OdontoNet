"""Historial cronológico del paciente (ODON-162).

Solo administración y doctores: incluye consultas y tratamientos, que
Recepción no ve (docs/PERMISSIONS.md).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.timeline_schema import EventType, TimelinePage
from app.services import timeline_service
from app.services.clinical_visit_service import get_clinic_patient

clinical_user = require_roles(Role.ADMIN, Role.DOCTOR)

router = APIRouter(prefix="/patients/{patient_id}/timeline", tags=["Timeline"])


@router.get("", response_model=TimelinePage)
def get_timeline(
    patient_id: int,
    types: Optional[list[EventType]] = Query(
        None, description="Tipos a incluir (se repite: ?types=visit&types=treatment). Por defecto, todos."
    ),
    cursor: Optional[str] = Query(None, description="next_cursor de la página anterior."),
    limit: int = Query(timeline_service.PAGE_SIZE, ge=1, le=timeline_service.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Eventos del paciente del más reciente al más antiguo, por páginas."""
    get_clinic_patient(db, patient_id, user.clinic_id)
    return timeline_service.get_timeline(db, patient_id, types, cursor, limit)
