"""Historial cronológico del paciente (ODON-162).

Une en una sola línea de tiempo, de lo más reciente a lo más antiguo:
consultas (atención, ediciones y anulación), cambios de estado de
tratamientos, versiones de la historia médica, citas atendidas o no
asistidas, fotografías clínicas (subida en ODON-174; corrección y
anulación en ODON-178) y periodontogramas finalizados o anulados (ODON-194;
los borradores no aparecen). Pagina por cursor (keyset): cada página es una consulta indexada,
sin OFFSET, aunque el paciente tenga años de historial.

Para sumar una fuente: agregar un SELECT a _EVENTS_SQL con (occurred_at, kind, source_id), su tipo a
EVENT_TYPES y su armado en _build.
"""
import base64
import binascii
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.appointment import Appointment
from app.models.clinical_visit import ClinicalVisit, ClinicalVisitRevision
from app.models.doctor import Doctor
from app.models.medical_history import PatientMedicalHistory
from app.models.patient_image import PatientImage, PatientImageRevision
from app.models.periodontal import PeriodontalExam
from app.models.treatment import Treatment, TreatmentStatusChange
from app.services.periodontal_service import summarize

PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Tipo visible (filtro) → prefijo de kind.
EVENT_TYPES = ("visit", "treatment", "medical_history", "appointment", "image", "periodontal")

_EVENTS_SQL = """
SELECT occurred_at, kind, source_id FROM (
    SELECT v.visit_at AS occurred_at, 'visit.attended' AS kind, v.id AS source_id
      FROM clinical_visits v WHERE v.patient_id = :patient_id
    UNION ALL
    SELECT r.edited_at, 'visit.edited', r.id
      FROM clinical_visit_revisions r JOIN clinical_visits v ON v.id = r.visit_id
     WHERE v.patient_id = :patient_id AND r.revision > 1
    UNION ALL
    SELECT v.voided_at, 'visit.voided', v.id
      FROM clinical_visits v WHERE v.patient_id = :patient_id AND v.voided_at IS NOT NULL
    UNION ALL
    SELECT c.changed_at, 'treatment.status', c.id
      FROM treatment_status_changes c JOIN treatments t ON t.id = c.treatment_id
     WHERE t.patient_id = :patient_id
    UNION ALL
    SELECT h.created_at, 'medical_history.version', h.id
      FROM patient_medical_histories h WHERE h.patient_id = :patient_id
    UNION ALL
    SELECT a.starts_at, 'appointment.' || a.status, a.id
      FROM appointments a
     WHERE a.patient_id = :patient_id AND a.status IN ('completed', 'no_show')
    UNION ALL
    SELECT i.uploaded_at, 'image.uploaded', i.id
      FROM patient_images i WHERE i.patient_id = :patient_id
    UNION ALL
    SELECT r.edited_at, 'image.edited', r.id
      FROM patient_image_revisions r JOIN patient_images i ON i.id = r.image_id
     WHERE i.patient_id = :patient_id AND r.revision > 1
    UNION ALL
    SELECT i.voided_at, 'image.voided', i.id
      FROM patient_images i WHERE i.patient_id = :patient_id AND i.voided_at IS NOT NULL
    UNION ALL
    SELECT e.finalized_at, 'periodontal.finalized', e.id
      FROM periodontal_exams e WHERE e.patient_id = :patient_id AND e.finalized_at IS NOT NULL
    UNION ALL
    SELECT e.voided_at, 'periodontal.voided', e.id
      FROM periodontal_exams e
     WHERE e.patient_id = :patient_id AND e.voided_at IS NOT NULL AND e.finalized_at IS NOT NULL
) AS events
WHERE split_part(kind, '.', 1) IN :types
  AND (CAST(:cursor_at AS timestamptz) IS NULL
       OR (occurred_at, kind, source_id) < (CAST(:cursor_at AS timestamptz), :cursor_kind, :cursor_id))
ORDER BY occurred_at DESC, kind DESC, source_id DESC
LIMIT :limit
"""

TREATMENT_LABELS = {
    "proposed": "propuesto",
    "accepted": "aceptado",
    "in_progress": "en curso",
    "completed": "completado",
    "cancelled": "cancelado",
}


def _encode_cursor(occurred_at: datetime, kind: str, source_id: int) -> str:
    raw = f"{occurred_at.isoformat()}|{kind}|{source_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str, int]:
    try:
        occurred_at, kind, source_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(occurred_at), kind, int(source_id)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cursor de paginación inválido.")


def _person(user) -> Optional[dict]:
    return {"id": user.id, "name": user.name} if user else None


def _tooth(treatment: Treatment) -> str:
    return f" (pieza {treatment.tooth})" if treatment.tooth else ""


def _load(db: Session, rows) -> dict:
    """Carga en lote los registros de cada tipo de la página."""
    # Las ediciones apuntan a la tabla de revisiones, no al registro principal.
    sources = {"visit.edited": "revision", "image.edited": "image_revision"}
    ids: dict[str, set[int]] = {}
    for row in rows:
        ids.setdefault(sources.get(row.kind, row.kind.split(".")[0]), set()).add(row.source_id)

    loaded = {}
    if "visit" in ids:
        loaded["visit"] = {
            v.id: v
            for v in db.query(ClinicalVisit)
            .options(joinedload(ClinicalVisit.doctor).joinedload(Doctor.user), joinedload(ClinicalVisit.created_by), joinedload(ClinicalVisit.voided_by))
            .filter(ClinicalVisit.id.in_(ids["visit"]))
        }
    if "revision" in ids:
        loaded["revision"] = {
            r.id: r
            for r in db.query(ClinicalVisitRevision)
            .options(joinedload(ClinicalVisitRevision.edited_by), joinedload(ClinicalVisitRevision.visit))
            .filter(ClinicalVisitRevision.id.in_(ids["revision"]))
        }
    if "treatment" in ids:
        loaded["treatment"] = {
            c.id: c
            for c in db.query(TreatmentStatusChange)
            .options(joinedload(TreatmentStatusChange.changed_by), joinedload(TreatmentStatusChange.treatment))
            .filter(TreatmentStatusChange.id.in_(ids["treatment"]))
        }
    if "medical_history" in ids:
        loaded["medical_history"] = {
            h.id: h
            for h in db.query(PatientMedicalHistory)
            .options(joinedload(PatientMedicalHistory.created_by))
            .filter(PatientMedicalHistory.id.in_(ids["medical_history"]))
        }
    if "appointment" in ids:
        loaded["appointment"] = {
            a.id: a
            for a in db.query(Appointment)
            .options(joinedload(Appointment.doctor).joinedload(Doctor.user))
            .filter(Appointment.id.in_(ids["appointment"]))
        }
    if "image" in ids:
        loaded["image"] = {
            i.id: i
            for i in db.query(PatientImage)
            .options(
                joinedload(PatientImage.uploaded_by),
                joinedload(PatientImage.clinical_visit),
                joinedload(PatientImage.voided_by),
            )
            .filter(PatientImage.id.in_(ids["image"]))
        }
    if "image_revision" in ids:
        loaded["image_revision"] = {
            r.id: r
            for r in db.query(PatientImageRevision)
            .options(joinedload(PatientImageRevision.edited_by))
            .filter(PatientImageRevision.id.in_(ids["image_revision"]))
        }
    if "periodontal" in ids:
        loaded["periodontal"] = {
            e.id: e
            for e in db.query(PeriodontalExam)
            .options(
                joinedload(PeriodontalExam.finalized_by),
                joinedload(PeriodontalExam.voided_by),
                selectinload(PeriodontalExam.teeth),
                selectinload(PeriodontalExam.sites),
            )
            .filter(PeriodontalExam.id.in_(ids["periodontal"]))
        }
    return loaded


def _periodontal_detail(exam: PeriodontalExam) -> Optional[str]:
    summary = summarize(exam)
    if summary["mean_probing_depth"] is None:
        return None
    parts = [f"Sondaje medio {_es(summary['mean_probing_depth'])} mm"]
    if summary["bleeding_pct"] is not None:
        parts.append(f"sangrado {_es(summary['bleeding_pct'])} %")
    return " · ".join(parts)


def _es(value: float) -> str:
    """Número con coma decimal y sin ceros sobrantes, como en la interfaz."""
    return f"{value:g}".replace(".", ",")


def _build(row, loaded: dict) -> dict:
    kind, source_id = row.kind, row.source_id
    event = {
        "id": f"{kind}:{source_id}",
        "type": kind.split(".")[0],
        "action": kind.split(".")[1],
        "occurred_at": row.occurred_at,
        "title": "",
        "detail": None,
        "actor": None,
        "ref_id": source_id,
        "voided": False,
    }

    if kind == "visit.attended":
        visit = loaded["visit"][source_id]
        event.update(
            title=f"Consulta: {visit.reason}",
            detail=visit.diagnosis,
            actor={"id": visit.doctor.id, "name": visit.doctor.user.name},
            voided=visit.voided_at is not None,
        )
    elif kind == "visit.edited":
        revision = loaded["revision"][source_id]
        event.update(
            title=f"Consulta editada: {revision.visit.reason}",
            detail=f"Revisión {revision.revision}",
            actor=_person(revision.edited_by),
            ref_id=revision.visit_id,
        )
    elif kind == "visit.voided":
        visit = loaded["visit"][source_id]
        event.update(
            title=f"Consulta anulada: {visit.reason}",
            detail=f"Motivo: {visit.void_reason}",
            actor=_person(visit.voided_by),
        )
    elif kind == "treatment.status":
        change = loaded["treatment"][source_id]
        treatment = change.treatment
        label = TREATMENT_LABELS[change.to_status]
        event.update(
            action=change.to_status,
            title=f"Tratamiento {label}: {treatment.procedure}{_tooth(treatment)}",
            detail=f"Motivo: {change.reason}" if change.reason else None,
            actor=_person(change.changed_by),
            ref_id=treatment.id,
        )
    elif kind == "medical_history.version":
        history = loaded["medical_history"][source_id]
        event.update(
            title="Historia médica registrada" if history.version == 1 else f"Historia médica actualizada (versión {history.version})",
            actor=_person(history.created_by),
            ref_id=history.version,
        )
    elif kind.startswith("appointment."):
        appointment = loaded["appointment"][source_id]
        attended = appointment.status == "completed"
        event.update(
            title=("Cita atendida" if attended else "No asistió a la cita")
            + (f": {appointment.reason}" if appointment.reason else ""),
            actor={"id": appointment.doctor.id, "name": appointment.doctor.user.name},
        )
    elif kind == "image.uploaded":
        image = loaded["image"][source_id]
        event.update(
            title="Fotografía clínica" + (f" (pieza {image.tooth})" if image.tooth else ""),
            detail=f"Consulta: {image.clinical_visit.reason}" if image.clinical_visit else None,
            actor=_person(image.uploaded_by),
            voided=image.voided_at is not None,
        )
    elif kind == "image.edited":
        revision = loaded["image_revision"][source_id]
        event.update(
            title="Datos de fotografía corregidos" + (f" (pieza {revision.tooth})" if revision.tooth else ""),
            detail=f"Revisión {revision.revision}",
            actor=_person(revision.edited_by),
            ref_id=revision.image_id,
        )
    elif kind == "image.voided":
        image = loaded["image"][source_id]
        event.update(
            title="Fotografía anulada" + (f" (pieza {image.tooth})" if image.tooth else ""),
            detail=f"Motivo: {image.void_reason}",
            actor=_person(image.voided_by),
        )
    elif kind == "periodontal.finalized":
        exam = loaded["periodontal"][source_id]
        event.update(
            title=f"Periodontograma del {exam.exam_date.strftime('%d/%m/%Y')}",
            detail=_periodontal_detail(exam),
            actor=_person(exam.finalized_by),
            voided=exam.voided_at is not None,
        )
    elif kind == "periodontal.voided":
        exam = loaded["periodontal"][source_id]
        event.update(
            title=f"Periodontograma anulado (examen del {exam.exam_date.strftime('%d/%m/%Y')})",
            detail=f"Motivo: {exam.void_reason}",
            actor=_person(exam.voided_by),
        )
    return event


def get_timeline(
    db: Session, patient_id: int, types: Optional[list[str]], cursor: Optional[str], limit: int
) -> dict:
    selected = tuple(types or EVENT_TYPES)
    cursor_at, cursor_kind, cursor_id = _decode_cursor(cursor) if cursor else (None, None, None)

    statement = text(_EVENTS_SQL).bindparams(bindparam("types", expanding=True))
    rows = db.execute(
        statement,
        {
            "patient_id": patient_id,
            "types": list(selected),
            "cursor_at": cursor_at,
            "cursor_kind": cursor_kind,
            "cursor_id": cursor_id,
            "limit": limit + 1,
        },
    ).all()

    has_more = len(rows) > limit
    rows = rows[:limit]
    loaded = _load(db, rows)
    last = rows[-1] if rows else None
    return {
        "items": [_build(row, loaded) for row in rows],
        "next_cursor": _encode_cursor(last.occurred_at, last.kind, last.source_id) if has_more else None,
    }
