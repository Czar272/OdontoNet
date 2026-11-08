"""Reportes de citas y pacientes (ODON-206).

Series agrupadas por día, semana (lunes) o mes en la zona horaria de la
clínica, con los mismos filtros de periodo y doctor que el panel de inicio
(`dashboard_service`). Solo datos agregados: ningún nombre de paciente.
"""
import csv
import io
from datetime import date, timedelta
from typing import Literal, Optional

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.services import audit_service
from app.services.dashboard_service import Period, resolve_doctor, resolve_period

Grouping = Literal["day", "week", "month"]

APPOINTMENT_STATUSES_ORDER = tuple(status.value for status in AppointmentStatus)

STATUS_LABELS = {
    "scheduled": "Programada",
    "confirmed": "Confirmada",
    "completed": "Atendida",
    "cancelled": "Cancelada",
    "no_show": "No asistió",
}


def bucket_start(day: date, group: Grouping) -> date:
    if group == "week":
        return day - timedelta(days=day.weekday())
    if group == "month":
        return day.replace(day=1)
    return day


def _next_bucket(start: date, group: Grouping) -> date:
    if group == "day":
        return start + timedelta(days=1)
    if group == "week":
        return start + timedelta(days=7)
    return (start.replace(day=28) + timedelta(days=4)).replace(day=1)


def buckets(period: Period, group: Grouping) -> list[tuple[date, date, date]]:
    """Todos los grupos del periodo, también los vacíos, como (inicio completo,
    desde, hasta). Los del borde se recortan al periodo y se marcan parciales:
    una semana o un mes a medias no debe parecer una caída de actividad."""
    result = []
    current = bucket_start(period.date_from, group)
    while current <= period.date_to:
        following = _next_bucket(current, group)
        result.append((current, max(current, period.date_from), min(following - timedelta(days=1), period.date_to)))
        current = following
    return result


def _bucket_fields(full_start: date, start: date, end: date, group: Grouping) -> dict:
    full_end = _next_bucket(full_start, group) - timedelta(days=1)
    return {"period_start": start, "period_end": end, "partial": (start, end) != (full_start, full_end)}


def _local_bucket(column, period: Period, group: Grouping):
    """Inicio del grupo (fecha) de un timestamptz, en la zona de la clínica."""
    local = func.timezone(str(period.zone), column)
    return cast(func.date_trunc(group, local), Date)


def _rate(part: int, total: int) -> Optional[float]:
    return round(100 * part / total, 1) if total else None


def _status_counts(rows) -> dict:
    counts = {status: 0 for status in APPOINTMENT_STATUSES_ORDER}
    for status, count in rows:
        counts[status] = counts.get(status, 0) + count
    return counts


def _with_totals(counts: dict) -> dict:
    attended = counts["completed"] + counts["no_show"]
    return {
        **counts,
        "total": sum(counts.values()),
        "attendance_rate": _rate(counts["completed"], attended),
        "no_show_rate": _rate(counts["no_show"], attended),
    }


def appointments_report(db: Session, clinic_id: int, date_from: Optional[date], date_to: Optional[date],
                        doctor_id: Optional[int], group: Grouping) -> dict:
    period = resolve_period(db, clinic_id, date_from, date_to)
    doctor = resolve_doctor(db, clinic_id, doctor_id)
    conditions = [
        Appointment.clinic_id == clinic_id,
        Appointment.starts_at >= period.start,
        Appointment.starts_at < period.end,
    ]
    if doctor is not None:
        conditions.append(Appointment.doctor_id == doctor.id)

    bucket = _local_bucket(Appointment.starts_at, period, group)
    per_bucket: dict[date, list] = {}
    for start, status, count in db.execute(
        select(bucket, Appointment.status, func.count()).where(*conditions).group_by(bucket, Appointment.status)
    ):
        per_bucket.setdefault(start, []).append((status, count))

    per_doctor: dict[int, list] = {}
    for doc_id, status, count in db.execute(
        select(Appointment.doctor_id, Appointment.status, func.count())
        .where(*conditions)
        .group_by(Appointment.doctor_id, Appointment.status)
    ):
        per_doctor.setdefault(doc_id, []).append((status, count))
    names = dict(db.execute(
        select(Doctor.id, User.name).join(User, User.id == Doctor.user_id).where(Doctor.id.in_(per_doctor))
    ).all()) if per_doctor else {}

    series = [
        {**_bucket_fields(full, start, end, group), **_with_totals(_status_counts(per_bucket.get(full, [])))}
        for full, start, end in buckets(period, group)
    ]
    by_doctor = sorted(
        (
            {"doctor": {"id": doc_id, "name": names.get(doc_id, "")}, **_with_totals(_status_counts(rows))}
            for doc_id, rows in per_doctor.items()
        ),
        key=lambda row: (-row["total"], row["doctor"]["id"]),
    )
    all_rows = [item for rows in per_doctor.values() for item in rows]
    return {
        "date_from": period.date_from,
        "date_to": period.date_to,
        "timezone": str(period.zone),
        "group": group,
        "doctor_id": doctor.id if doctor else None,
        "series": series,
        "by_doctor": by_doctor,
        "totals": _with_totals(_status_counts(all_rows)),
    }


def patients_report(db: Session, clinic_id: int, date_from: Optional[date], date_to: Optional[date],
                    doctor_id: Optional[int], group: Grouping) -> dict:
    """Pacientes nuevos por fecha de alta; con doctor, los asignados a él."""
    period = resolve_period(db, clinic_id, date_from, date_to)
    doctor = resolve_doctor(db, clinic_id, doctor_id)
    conditions = [Patient.clinic_id == clinic_id]
    if doctor is not None:
        conditions.append(Patient.doctor_id == doctor.id)

    bucket = _local_bucket(Patient.created_at, period, group)
    counts = dict(db.execute(
        select(bucket, func.count()).where(
            *conditions, Patient.created_at >= period.start, Patient.created_at < period.end
        ).group_by(bucket)
    ).all())
    without_date = db.execute(
        select(func.count()).select_from(Patient).where(*conditions, Patient.created_at.is_(None))
    ).scalar() or 0

    series = [
        {**_bucket_fields(full, start, end, group), "new_patients": counts.get(full, 0)}
        for full, start, end in buckets(period, group)
    ]
    return {
        "date_from": period.date_from,
        "date_to": period.date_to,
        "timezone": str(period.zone),
        "group": group,
        "doctor_id": doctor.id if doctor else None,
        "series": series,
        "total_new": sum(counts.values()),
        "without_registration_date": without_date,
    }


GROUP_LABELS = {"day": "Día", "week": "Semana (lunes)", "month": "Mes"}


FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value):
    """Un texto que una hoja de cálculo interpretaría como fórmula lleva un
    apóstrofo delante (inyección CSV). Los números no se tocan."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _csv(rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerows([[_safe_cell(cell) for cell in row] for row in rows])
    # BOM: Excel abre el archivo en UTF-8 (tildes y «ñ» correctas).
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _rate_cell(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.1f}"


def appointments_csv(report: dict) -> bytes:
    statuses = list(APPOINTMENT_STATUSES_ORDER)
    header = ["Tipo", "Grupo", "Hasta", *[STATUS_LABELS[s] for s in statuses], "Total", "Asistencia %",
              "Inasistencia %"]
    rows: list[list] = [header]
    for item in report["series"]:
        rows.append([GROUP_LABELS[report["group"]] + (" (parcial)" if item["partial"] else ""),
                     item["period_start"].isoformat(), item["period_end"].isoformat(),
                     *[item[s] for s in statuses], item["total"],
                     _rate_cell(item["attendance_rate"]), _rate_cell(item["no_show_rate"])])
    for item in report["by_doctor"]:
        rows.append(["Doctor", item["doctor"]["name"], "", *[item[s] for s in statuses], item["total"],
                     _rate_cell(item["attendance_rate"]), _rate_cell(item["no_show_rate"])])
    totals = report["totals"]
    rows.append(["Total", report["date_from"].isoformat(), report["date_to"].isoformat(),
                 *[totals[s] for s in statuses], totals["total"],
                 _rate_cell(totals["attendance_rate"]), _rate_cell(totals["no_show_rate"])])
    return _csv(rows)


def patients_csv(report: dict) -> bytes:
    rows: list[list] = [[GROUP_LABELS[report["group"]], "Hasta", "Parcial", "Pacientes nuevos"]]
    rows += [[item["period_start"].isoformat(), item["period_end"].isoformat(), "sí" if item["partial"] else "no",
              item["new_patients"]] for item in report["series"]]
    rows.append(["Total", report["date_to"].isoformat(), "", report["total_new"]])
    rows.append(["Sin fecha de alta (anteriores al registro)", "", "", report["without_registration_date"]])
    return _csv(rows)


def log_export(db: Session, kind: str, user: User, report: dict) -> None:
    """Registra la exportación en la auditoría persistente (ODON-222) y la confirma.

    Un reporte agregado no es una fila de la base: entity_id queda vacío y el
    tipo de reporte («appointments» o «patients») va como único elemento de
    `fields`, para poder filtrarlo sin una columna nueva. Los filtros usados
    (doctor, fechas, agrupación) solo van al log."""
    audit_service.record(
        db, user, "report.exported", "report", None, fields=[kind],
        detail=(
            f"kind={kind} doctor_id={report['doctor_id']} from={report['date_from']} "
            f"to={report['date_to']} group={report['group']}"
        ),
    )
    db.commit()
