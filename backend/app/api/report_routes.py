"""Reportes de citas y pacientes (ODON-206).

Consultar: los tres roles (datos agregados, como el panel de inicio).
Exportar a CSV: solo administración; cada exportación queda en auditoría.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.permissions import ALL_ROLES, Role, require_roles
from app.database.dependencies import get_db
from app.models.user import User
from app.schemas.report_schema import AppointmentsReport, Grouping, PatientsReport
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])

any_user = require_roles(*ALL_ROLES)
admin_user = require_roles(Role.ADMIN)

FROM = Query(None, alias="from", description="Fecha local inicial (incluida). Por defecto, el día 1 del mes en curso.")
TO = Query(None, alias="to", description="Fecha local final (incluida). Por defecto, el fin del mes de la fecha inicial.")
DOCTOR = Query(None, description="Limita el reporte a un doctor de la clínica.")
GROUP = Query("day", description="Agrupación en la zona de la clínica: day, week (desde el lunes) o month.")

CSV_RESPONSES = {200: {"content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
                       "description": "Archivo CSV agregado"}}


def _csv_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/appointments", response_model=AppointmentsReport)
def appointments(
    date_from: Optional[date] = FROM, date_to: Optional[date] = TO, doctor_id: Optional[int] = DOCTOR,
    group: Grouping = GROUP, db: Session = Depends(get_db), user: User = Depends(any_user),
):
    """Citas por grupo de fechas y estado, y por doctor."""
    return report_service.appointments_report(db, user.clinic_id, date_from, date_to, doctor_id, group)


@router.get("/patients", response_model=PatientsReport)
def patients(
    date_from: Optional[date] = FROM, date_to: Optional[date] = TO, doctor_id: Optional[int] = DOCTOR,
    group: Grouping = GROUP, db: Session = Depends(get_db), user: User = Depends(any_user),
):
    """Pacientes nuevos por grupo de fechas (por fecha de alta)."""
    return report_service.patients_report(db, user.clinic_id, date_from, date_to, doctor_id, group)


@router.get("/appointments.csv", response_class=Response, responses=CSV_RESPONSES)
def appointments_csv(
    date_from: Optional[date] = FROM, date_to: Optional[date] = TO, doctor_id: Optional[int] = DOCTOR,
    group: Grouping = GROUP, db: Session = Depends(get_db), user: User = Depends(admin_user),
):
    """El reporte de citas en CSV (solo administración)."""
    report = report_service.appointments_report(db, user.clinic_id, date_from, date_to, doctor_id, group)
    report_service.log_export("appointments", user, report)
    filename = f"reporte-citas-{report['date_from'].isoformat()}-{report['date_to'].isoformat()}.csv"
    return _csv_response(report_service.appointments_csv(report), filename)


@router.get("/patients.csv", response_class=Response, responses=CSV_RESPONSES)
def patients_csv(
    date_from: Optional[date] = FROM, date_to: Optional[date] = TO, doctor_id: Optional[int] = DOCTOR,
    group: Grouping = GROUP, db: Session = Depends(get_db), user: User = Depends(admin_user),
):
    """El reporte de pacientes nuevos en CSV (solo administración)."""
    report = report_service.patients_report(db, user.clinic_id, date_from, date_to, doctor_id, group)
    report_service.log_export("patients", user, report)
    filename = f"reporte-pacientes-{report['date_from'].isoformat()}-{report['date_to'].isoformat()}.csv"
    return _csv_response(report_service.patients_csv(report), filename)
