"""Consulta de la auditoría (ODON-222).

Administración ve todos los eventos de su clínica; un doctor, solo sus propias
acciones (decisión del desarrollador); recepción no accede. Solo lectura: la
auditoría no se edita ni se borra.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.clinic import Clinic
from app.models.user import User
from app.schemas.audit_schema import AuditPage
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])

audit_reader = require_roles(Role.ADMIN, Role.DOCTOR)


def _local_midnight(db: Session, clinic_id: int, day: date) -> datetime:
    zone = ZoneInfo(db.get(Clinic, clinic_id).timezone)
    return datetime.combine(day, time.min, zone)


@router.get("", response_model=AuditPage)
def list_audit_events(
    date_from: Optional[date] = Query(None, alias="from", description="Fecha local inicial (incluida)."),
    date_to: Optional[date] = Query(None, alias="to", description="Fecha local final (incluida)."),
    actor_user_id: Optional[int] = Query(None, description="Solo administración: eventos de un usuario."),
    action: Optional[str] = Query(None, max_length=60),
    entity_type: Optional[str] = Query(None, max_length=40),
    patient_id: Optional[int] = None,
    cursor: Optional[str] = Query(None, description="next_cursor de la página anterior."),
    limit: int = Query(audit_service.PAGE_SIZE, ge=1, le=audit_service.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user: User = Depends(audit_reader),
):
    """Eventos de auditoría del más reciente al más antiguo, por páginas."""
    if date_to is not None and date_to >= date.max:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Fecha final inválida.")
    # Un doctor solo ve lo que hizo él, aunque pida otro usuario.
    actor = user.id if user.role == Role.DOCTOR.value else actor_user_id
    return audit_service.list_events(
        db,
        user.clinic_id,
        actor_user_id=actor,
        action=action,
        entity_type=entity_type,
        patient_id=patient_id,
        date_from=_local_midnight(db, user.clinic_id, date_from) if date_from else None,
        date_to=_local_midnight(db, user.clinic_id, date_to + timedelta(days=1)) if date_to else None,
        cursor=cursor,
        limit=limit,
    )
