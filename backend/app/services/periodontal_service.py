"""Periodontograma manual: exámenes en borrador, finalizados y anulados (ODON-9).

Reglas:
- Administración y doctores leen y crean exámenes; el borrador lo editan,
  finalizan o anulan solo su autor o administración.
- Cada guardado del borrador exige base_revision (409 con current_revision si
  otra persona guardó antes) y copia el examen completo como revisión.
- Un examen finalizado es inmutable; para corregirlo se anula con motivo y se
  registra otro. Nada se borra.
- El resumen es estadística descriptiva, no un diagnóstico.
"""
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.permissions import Role
from app.models.clinic import Clinic
from app.models.clinical_visit import ClinicalVisit
from app.models.patient import Patient
from app.models.periodontal import (
    PERMANENT_TEETH,
    SITES,
    PeriodontalExam,
    PeriodontalExamRevision,
    PeriodontalSite,
    PeriodontalTooth,
)
from app.models.user import User
from app.schemas.periodontal_schema import ExamContent, ExamUpdate, SiteData, ToothData
from app.services import audit_service

FURCATION_COLUMNS = ("b", "mp", "dp", "l")
SITE_FIELDS = ("probing_depth", "gingival_margin", "bleeding", "suppuration", "plaque", "source")
# Umbral descriptivo de «sitio profundo» del resumen (acordado en ODON-9).
DEEP_SITE_MM = 4


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _person(user: Optional[User]) -> Optional[dict]:
    return {"id": user.id, "name": user.name} if user else None


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def _exams(db: Session):
    return db.query(PeriodontalExam).options(
        joinedload(PeriodontalExam.created_by),
        joinedload(PeriodontalExam.finalized_by),
        joinedload(PeriodontalExam.voided_by),
        joinedload(PeriodontalExam.clinical_visit),
        selectinload(PeriodontalExam.teeth),
        selectinload(PeriodontalExam.sites),
    )


def list_exams(db: Session, patient_id: int) -> list[PeriodontalExam]:
    return (
        _exams(db)
        .filter(PeriodontalExam.patient_id == patient_id)
        .order_by(PeriodontalExam.exam_date.desc(), PeriodontalExam.id.desc())
        .all()
    )


def get_exam(db: Session, patient_id: int, exam_id: int) -> PeriodontalExam:
    exam = _exams(db).filter(PeriodontalExam.id == exam_id, PeriodontalExam.patient_id == patient_id).first()
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Periodontograma no encontrado.")
    return exam


# --- Lectura -----------------------------------------------------------------


def _attachment_level(site: PeriodontalSite) -> Optional[int]:
    if site.probing_depth is None or site.gingival_margin is None:
        return None
    return site.probing_depth - site.gingival_margin


def _site_dict(site: PeriodontalSite) -> dict:
    return {**{field: getattr(site, field) for field in SITE_FIELDS}, "attachment_level": _attachment_level(site)}


def _tooth_dict(tooth: PeriodontalTooth, sites: dict[str, PeriodontalSite]) -> dict:
    return {
        "tooth": tooth.tooth,
        "missing": tooth.missing,
        "implant": tooth.implant,
        "mobility": tooth.mobility,
        "furcation": {entrance: getattr(tooth, f"furcation_{entrance}") for entrance in FURCATION_COLUMNS},
        "note": tooth.note,
        "source": tooth.source,
        "sites": {code: _site_dict(sites[code]) for code in SITES},
    }


def _pct(part: int, total: int) -> Optional[float]:
    return round(100 * part / total, 1) if total else None


def _mean(values: list[int]) -> Optional[float]:
    return round(sum(values) / len(values), 2) if values else None


def summarize(exam: PeriodontalExam) -> dict:
    """Promedios y porcentajes sobre los sitios con sondaje registrado de las piezas presentes."""
    missing = {tooth.tooth for tooth in exam.teeth if tooth.missing}
    measured = [site for site in exam.sites if site.tooth not in missing and site.probing_depth is not None]
    levels = [level for level in (_attachment_level(site) for site in measured) if level is not None]
    return {
        "present_teeth": len(PERMANENT_TEETH) - len(missing),
        "measured_sites": len(measured),
        "mean_probing_depth": _mean([site.probing_depth for site in measured]),
        "mean_attachment_level": _mean(levels),
        "bleeding_pct": _pct(sum(site.bleeding for site in measured), len(measured)),
        "plaque_pct": _pct(sum(site.plaque for site in measured), len(measured)),
        "deep_sites_pct": _pct(sum(site.probing_depth >= DEEP_SITE_MM for site in measured), len(measured)),
        "default_sites": sum(site.source == "default" for site in measured),
    }


def _ordered_teeth(exam: PeriodontalExam) -> list[dict]:
    sites: dict[int, dict[str, PeriodontalSite]] = {}
    for site in exam.sites:
        sites.setdefault(site.tooth, {})[site.site] = site
    by_tooth = {tooth.tooth: tooth for tooth in exam.teeth}
    return [_tooth_dict(by_tooth[number], sites[number]) for number in PERMANENT_TEETH]


def to_list_item(exam: PeriodontalExam) -> dict:
    visit = exam.clinical_visit
    return {
        "id": exam.id,
        "patient_id": exam.patient_id,
        "exam_date": exam.exam_date,
        "clinical_visit": (
            {"id": visit.id, "reason": visit.reason, "visit_at": visit.visit_at} if visit else None
        ),
        "notes": exam.notes,
        "status": exam.status,
        "revision": exam.revision,
        "created_by": _person(exam.created_by),
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
        "finalized_by": _person(exam.finalized_by),
        "finalized_at": exam.finalized_at,
        "voided_by": _person(exam.voided_by),
        "voided_at": exam.voided_at,
        "void_reason": exam.void_reason,
        "summary": summarize(exam),
    }


def to_response(exam: PeriodontalExam) -> dict:
    return {**to_list_item(exam), "teeth": _ordered_teeth(exam)}


def list_revisions(db: Session, exam: PeriodontalExam) -> list[dict]:
    revisions = (
        db.query(PeriodontalExamRevision)
        .options(joinedload(PeriodontalExamRevision.edited_by))
        .filter(PeriodontalExamRevision.exam_id == exam.id)
        .order_by(PeriodontalExamRevision.revision.desc())
        .all()
    )
    return [
        {"revision": rev.revision, "edited_by": _person(rev.edited_by), "edited_at": rev.edited_at}
        for rev in revisions
    ]


# --- Escritura ---------------------------------------------------------------


def _ensure_editable_patient(patient: Patient) -> None:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para registrar o modificar periodontogramas.",
        )


def _clinic_today(db: Session, clinic_id: int) -> date:
    clinic = db.get(Clinic, clinic_id)
    return datetime.now(timezone.utc).astimezone(ZoneInfo(clinic.timezone)).date()


def _validate_content(db: Session, patient: Patient, data: ExamContent, current_visit_id=None) -> None:
    if data.exam_date > _clinic_today(db, patient.clinic_id):
        raise _unprocessable("La fecha del periodontograma no puede ser futura.")
    # La consulta solo se valida si cambia: se conserva aunque se anule después.
    if data.clinical_visit_id is not None and data.clinical_visit_id != current_visit_id:
        visit = (
            db.query(ClinicalVisit)
            .filter(ClinicalVisit.id == data.clinical_visit_id, ClinicalVisit.patient_id == patient.id)
            .first()
        )
        if visit is None:
            raise _unprocessable("La consulta no pertenece a este paciente.")
        if visit.voided_at is not None:
            raise _unprocessable("La consulta está anulada.")


def _content_by_tooth(data: ExamContent) -> dict[int, ToothData]:
    given = {tooth.tooth: tooth for tooth in data.teeth}
    return {number: given.get(number) or ToothData(tooth=number) for number in PERMANENT_TEETH}


def _apply(exam: PeriodontalExam, data: ExamContent) -> bool:
    """Copia el contenido al examen y sus filas. Devuelve si algo cambió."""
    changed = False

    def assign(target, field, value):
        nonlocal changed
        if getattr(target, field) != value:
            setattr(target, field, value)
            changed = True

    assign(exam, "exam_date", data.exam_date)
    assign(exam, "clinical_visit_id", data.clinical_visit_id)
    assign(exam, "notes", data.notes)

    content = _content_by_tooth(data)
    teeth = {tooth.tooth: tooth for tooth in exam.teeth}
    sites = {(site.tooth, site.site): site for site in exam.sites}
    for number, tooth_data in content.items():
        tooth = teeth[number]
        assign(tooth, "missing", tooth_data.missing)
        assign(tooth, "implant", tooth_data.implant)
        assign(tooth, "mobility", tooth_data.mobility)
        assign(tooth, "note", tooth_data.note)
        assign(tooth, "source", tooth_data.source if tooth_data.mobility is not None else "manual")
        for entrance in FURCATION_COLUMNS:
            assign(tooth, f"furcation_{entrance}", getattr(tooth_data.furcation, entrance))
        for code in SITES:
            site_data = tooth_data.sites.get(code) or SiteData()
            if site_data.is_empty():
                # Un sitio vacío no tiene origen que conservar.
                site_data = SiteData()
            for field in SITE_FIELDS:
                assign(sites[(number, code)], field, getattr(site_data, field))
    return changed


def snapshot(exam: PeriodontalExam) -> dict:
    """Examen completo en JSON, tal como se guarda en cada revisión."""
    return {
        "exam_date": exam.exam_date.isoformat(),
        "clinical_visit_id": exam.clinical_visit_id,
        "notes": exam.notes,
        "teeth": [
            {key: value for key, value in tooth.items() if key != "sites"}
            | {"sites": {code: {f: s[f] for f in SITE_FIELDS} for code, s in tooth["sites"].items()}}
            for tooth in _ordered_teeth(exam)
        ],
    }


def _add_revision(db: Session, exam: PeriodontalExam, editor: User) -> None:
    db.add(
        PeriodontalExamRevision(
            clinic_id=exam.clinic_id,
            exam_id=exam.id,
            revision=exam.revision,
            data=snapshot(exam),
            edited_by_user_id=editor.id,
        )
    )


def create_exam(db: Session, patient: Patient, data: ExamContent, author: User) -> PeriodontalExam:
    _ensure_editable_patient(patient)
    _validate_content(db, patient, data)

    exam = PeriodontalExam(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        exam_date=data.exam_date,
        created_by_user_id=author.id,
    )
    exam.teeth = [PeriodontalTooth(clinic_id=patient.clinic_id, tooth=number) for number in PERMANENT_TEETH]
    exam.sites = [
        PeriodontalSite(clinic_id=patient.clinic_id, tooth=number, site=code)
        for number in PERMANENT_TEETH
        for code in SITES
    ]
    db.add(exam)
    db.flush()
    _apply(exam, data)
    db.flush()
    _add_revision(db, exam, author)
    audit_service.record(
        db, author, "periodontal_exam.created", "periodontal_exam", exam.id,
        patient_id=patient.id, clinic_id=patient.clinic_id,
    )
    db.commit()

    return get_exam(db, patient.id, exam.id)


def _lock(db: Session, exam: PeriodontalExam) -> PeriodontalExam:
    """Bloquea la fila del examen: guardados, finalización y anulación no se cruzan."""
    db.execute(select(PeriodontalExam.id).where(PeriodontalExam.id == exam.id).with_for_update())
    db.refresh(exam)
    return exam


def _ensure_can_modify(exam: PeriodontalExam, user: User) -> None:
    if user.role != Role.ADMIN.value and exam.created_by_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo quien registró el periodontograma o administración pueden modificarlo.",
        )
    if exam.voided_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El periodontograma está anulado."
        )


def _ensure_draft(exam: PeriodontalExam) -> None:
    if exam.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El periodontograma está finalizado y no se puede modificar. Anúlalo y registra otro.",
        )


def _revision_conflict(current: int) -> HTTPException:
    exc = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="El periodontograma cambió mientras lo editabas. Revisa la versión actual antes de guardar.",
    )
    exc.extra = {"current_revision": current}
    return exc


def _check_revision(db: Session, exam: PeriodontalExam, base_revision: int) -> None:
    if base_revision != exam.revision:
        current = exam.revision
        db.rollback()
        raise _revision_conflict(current)


def update_exam(
    db: Session, patient: Patient, exam: PeriodontalExam, data: ExamUpdate, editor: User
) -> PeriodontalExam:
    exam = _lock(db, exam)
    try:
        _ensure_editable_patient(patient)
        _ensure_can_modify(exam, editor)
        _ensure_draft(exam)
    except HTTPException:
        db.rollback()
        raise
    _check_revision(db, exam, data.base_revision)
    try:
        _validate_content(db, patient, data, current_visit_id=exam.clinical_visit_id)
    except HTTPException:
        db.rollback()
        raise

    if not _apply(exam, data):
        db.rollback()
        return get_exam(db, patient.id, exam.id)

    exam.revision += 1
    exam.updated_at = datetime.now(timezone.utc)
    db.flush()
    _add_revision(db, exam, editor)
    try:
        db.flush()
        audit_service.record(
            db, editor, "periodontal_exam.updated", "periodontal_exam", exam.id,
            patient_id=patient.id, clinic_id=patient.clinic_id, detail=f"revision={exam.revision}",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_periodontal_revisions_exam_revision" not in str(exc.orig):
            raise
        raise _revision_conflict(get_exam(db, patient.id, exam.id).revision)

    return get_exam(db, patient.id, exam.id)


def finalize_exam(
    db: Session, patient: Patient, exam: PeriodontalExam, base_revision: int, user: User
) -> PeriodontalExam:
    exam = _lock(db, exam)
    try:
        _ensure_editable_patient(patient)
        _ensure_can_modify(exam, user)
        _ensure_draft(exam)
    except HTTPException:
        db.rollback()
        raise
    _check_revision(db, exam, base_revision)
    if not any(site.probing_depth is not None for site in exam.sites):
        db.rollback()
        raise _unprocessable("Registra al menos una profundidad de sondaje antes de finalizar.")

    exam.status = "final"
    exam.finalized_at = datetime.now(timezone.utc)
    exam.updated_at = exam.finalized_at
    exam.finalized_by_user_id = user.id
    audit_service.record(
        db, user, "periodontal_exam.finalized", "periodontal_exam", exam.id,
        patient_id=patient.id, fields=["status"], clinic_id=patient.clinic_id,
    )
    db.commit()

    return get_exam(db, patient.id, exam.id)


def export_report(db: Session, patient: Patient, exam: PeriodontalExam, user: User) -> bytes:
    """PDF de un examen finalizado y vigente (ODON-198). Queda en el registro de auditoría."""
    if exam.voided_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El periodontograma está anulado.")
    if exam.status != "final":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Finaliza el periodontograma para exportarlo."
        )
    from app.services.periodontal_report import build_report  # reportlab solo se carga al exportar

    content = build_report(exam, patient, db.get(Clinic, patient.clinic_id))
    # La exportación no cambia datos: el commit solo persiste el evento (ODON-222).
    audit_service.record(
        db, user, "periodontal_exam.exported", "periodontal_exam", exam.id,
        patient_id=patient.id, clinic_id=patient.clinic_id,
    )
    db.commit()
    return content


def void_exam(db: Session, patient: Patient, exam: PeriodontalExam, reason: str, user: User) -> PeriodontalExam:
    exam = _lock(db, exam)
    try:
        _ensure_editable_patient(patient)
        _ensure_can_modify(exam, user)
    except HTTPException:
        db.rollback()
        raise

    exam.voided_at = datetime.now(timezone.utc)
    exam.updated_at = exam.voided_at
    exam.voided_by_user_id = user.id
    exam.void_reason = reason
    # El motivo no se guarda en la auditoría: solo el nombre del campo.
    audit_service.record(
        db, user, "periodontal_exam.voided", "periodontal_exam", exam.id,
        patient_id=patient.id, fields=["void_reason", "voided_at"], clinic_id=patient.clinic_id,
    )
    db.commit()

    return get_exam(db, patient.id, exam.id)
