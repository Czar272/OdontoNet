"""Panel de inicio (ODON-202).

Lo ven los tres roles: devuelve conteos agregados y la agenda de hoy, que
Recepción ya ve en la agenda. No expone contenido del expediente.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import ALL_ROLES, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.dashboard_schema import DashboardRead
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(
    date_from: Optional[date] = Query(None, alias="from", description="Fecha local inicial (incluida). Por defecto, el día 1 del mes en curso."),
    date_to: Optional[date] = Query(None, alias="to", description="Fecha local final (incluida). Por defecto, el fin del mes de la fecha inicial."),
    doctor_id: Optional[int] = Query(None, description="Limita los indicadores a un doctor de la clínica."),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ALL_ROLES)),
):
    """Indicadores del periodo y agenda de hoy, en la zona horaria de la clínica."""
    return dashboard_service.dashboard(db, user.clinic_id, date_from, date_to, doctor_id)
