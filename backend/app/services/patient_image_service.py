"""Imágenes clínicas del paciente (ODON-166, ODON-170, ODON-174, ODON-178).

Guarda el archivo en el almacenamiento privado y su registro en la base como
una sola operación: si la base falla, el archivo recién escrito se descarta.
Subir exige un consentimiento vigente y pasa por el saneamiento de
image_processing. El archivo nunca cambia: los metadatos se corrigen con
revisiones y una foto errónea se anula con motivo. Las imágenes no se borran.
"""
import hashlib
import logging
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.permissions import Role
from app.models.clinic import Clinic
from app.models.clinical_visit import ClinicalVisit
from app.models.patient import Patient
from app.models.patient_image import (
    IMAGE_METADATA_FIELDS,
    IMAGE_ORIGINS,
    IMAGE_TYPES,
    IMAGE_VIEWS,
    ImageAccessLog,
    PatientImage,
    PatientImageRevision,
    image_max_bytes,
)
from app.models.treatment import is_valid_tooth
from app.models.user import User
from app.schemas.patient_image_schema import PatientImageUpdate
from app.services import audit_service
from app.services.image_processing import make_thumbnail, sanitize_image
from app.services.image_storage import ImageStorage, StoredImageNotFound
from app.services.photo_consent_service import require_active_consent
logger = logging.getLogger(__name__)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def _images(db: Session):
    return db.query(PatientImage).options(
        joinedload(PatientImage.clinical_visit),
        joinedload(PatientImage.uploaded_by),
        joinedload(PatientImage.voided_by),
    )


def list_images(db: Session, patient_id: int) -> list[PatientImage]:
    """Imágenes del paciente, la más reciente primero."""
    return (
        _images(db)
        .filter(PatientImage.patient_id == patient_id)
        .order_by(PatientImage.uploaded_at.desc(), PatientImage.id.desc())
        .all()
    )


def get_image(db: Session, patient_id: int, image_id: int) -> PatientImage:
    image = (
        _images(db)
        .filter(PatientImage.id == image_id, PatientImage.patient_id == patient_id)
        .first()
    )
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    return image


def to_response(image: PatientImage) -> dict:
    visit = image.clinical_visit
    return {
        "id": image.id,
        "patient_id": image.patient_id,
        "clinical_visit": (
            {"id": visit.id, "visit_at": visit.visit_at, "reason": visit.reason, "voided": visit.voided_at is not None}
            if visit
            else None
        ),
        "tooth": image.tooth,
        "origin": image.origin,
        "view": image.view,
        "taken_on": image.taken_on,
        "revision": image.revision,
        "content_type": image.content_type,
        "size_bytes": image.size_bytes,
        "width": image.width,
        "height": image.height,
        "consent_id": image.consent_id,
        "uploaded_by": {"id": image.uploaded_by.id, "name": image.uploaded_by.name},
        "uploaded_at": image.uploaded_at,
        "voided_at": image.voided_at,
        "voided_by": {"id": image.voided_by.id, "name": image.voided_by.name} if image.voided_by else None,
        "void_reason": image.void_reason,
    }


def check_size(data: bytes) -> None:
    if not data:
        raise _unprocessable("La imagen está vacía.")
    max_bytes = image_max_bytes()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"La imagen supera el máximo de {max_bytes // (1024 * 1024)} MB.",
        )


def _validate_context(db: Session, patient: Patient, visit_id, tooth, action: str = "agregar imágenes") -> None:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El paciente está archivado. Reactívalo para {action}.",
        )
    if tooth is not None and not is_valid_tooth(tooth):
        raise _unprocessable("La pieza dental no es válida (numeración FDI).")
    if visit_id is not None:
        visit = (
            db.query(ClinicalVisit)
            .filter(ClinicalVisit.id == visit_id, ClinicalVisit.patient_id == patient.id)
            .first()
        )
        if visit is None:
            raise _unprocessable("La consulta no pertenece a este paciente.")
        if visit.voided_at is not None:
            raise _unprocessable("La consulta está anulada.")


def _validate_metadata(db: Session, patient: Patient, origin, view, taken_on: Optional[date]) -> None:
    """Origen obligatorio, vista opcional y fecha de toma no futura (ODON-178)."""
    if origin is None:
        raise _unprocessable("Indica el origen de la fotografía.")
    if origin not in IMAGE_ORIGINS:
        raise _unprocessable("El origen de la fotografía no es válido.")
    if view is not None and view not in IMAGE_VIEWS:
        raise _unprocessable("El tipo de vista no es válido.")
    if taken_on is not None:
        clinic = db.get(Clinic, patient.clinic_id)
        today = datetime.now(timezone.utc).astimezone(ZoneInfo(clinic.timezone)).date()
        if taken_on > today:
            raise _unprocessable("La fecha de toma no puede ser futura.")


def _add_revision(db: Session, image: PatientImage, editor: User) -> None:
    db.add(
        PatientImageRevision(
            clinic_id=image.clinic_id,
            image_id=image.id,
            revision=image.revision,
            edited_by_user_id=editor.id,
            **{field: getattr(image, field) for field in IMAGE_METADATA_FIELDS},
        )
    )


def store_image(
    db: Session,
    storage: ImageStorage,
    patient: Patient,
    data: bytes,
    content_type: str,
    width: int,
    height: int,
    author: User,
    consent_id: int,
    clinical_visit_id: Optional[int] = None,
    tooth: Optional[int] = None,
    thumbnail: Optional[bytes] = None,
    origin: Optional[str] = None,
    view: Optional[str] = None,
    taken_on: Optional[date] = None,
) -> PatientImage:
    """Valida, guarda el archivo (y su miniatura) y registra la imagen.

    El tipo y las dimensiones los determina quien llama a partir del contenido
    real del archivo (upload_image), no de lo que declare el cliente."""
    _validate_context(db, patient, clinical_visit_id, tooth)
    if content_type not in IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo de imagen no permitido. Usa JPEG, PNG o WebP.",
        )
    check_size(data)

    key = storage.save(patient.clinic_id, data, IMAGE_TYPES[content_type])
    keys = [key]
    thumbnail_key = None
    try:
        if thumbnail is not None:
            thumbnail_key = storage.save(patient.clinic_id, thumbnail, "jpg")
            keys.append(thumbnail_key)
    except Exception:
        storage.discard(key)
        raise
    image = PatientImage(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        clinical_visit_id=clinical_visit_id,
        tooth=tooth,
        origin=origin,
        view=view,
        taken_on=taken_on,
        revision=1,
        storage_key=key,
        thumbnail_key=thumbnail_key,
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
        consent_id=consent_id,
        uploaded_by_user_id=author.id,
    )
    try:
        db.add(image)
        db.flush()
        _add_revision(db, image, author)
        audit_service.record(
            db, author, "image.stored", "image", image.id,
            patient_id=patient.id, clinic_id=patient.clinic_id,
            detail=f"patient_id={patient.id} bytes={image.size_bytes}",
        )
        db.commit()
    except Exception:
        db.rollback()
        for saved in keys:
            storage.discard(saved)
        raise
    db.refresh(image)
    return image


def upload_image(
    db: Session,
    storage: ImageStorage,
    patient: Patient,
    raw: bytes,
    filename: str,
    author: User,
    clinical_visit_id: Optional[int] = None,
    tooth: Optional[int] = None,
    origin: Optional[str] = None,
    view: Optional[str] = None,
    taken_on: Optional[date] = None,
) -> PatientImage:
    """Subida desde la API: contexto, metadatos, consentimiento, tamaño y saneamiento.

    Las validaciones baratas van antes de abrir la imagen con Pillow."""
    _validate_context(db, patient, clinical_visit_id, tooth)
    _validate_metadata(db, patient, origin, view, taken_on)
    consent = require_active_consent(db, patient)
    check_size(raw)
    processed = sanitize_image(raw, filename)
    image = store_image(
        db,
        storage,
        patient,
        processed.data,
        processed.content_type,
        width=processed.width,
        height=processed.height,
        author=author,
        consent_id=consent.id,
        clinical_visit_id=clinical_visit_id,
        tooth=tooth,
        thumbnail=make_thumbnail(processed.data),
        origin=origin,
        view=view,
        taken_on=taken_on,
    )
    return _images(db).filter(PatientImage.id == image.id).one()


def read_image_file(storage: ImageStorage, image: PatientImage) -> bytes:
    try:
        return storage.read(image.storage_key)
    except StoredImageNotFound:
        # Registro sin archivo: respaldo incompleto o restauración parcial.
        logger.error("Archivo de imagen faltante image_id=%s key=%s", image.id, image.storage_key)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo de la imagen no está disponible. Avisa a administración.",
        )


def read_thumbnail(db: Session, storage: ImageStorage, image: PatientImage) -> bytes:
    """Miniatura de la galería (ODON-174).

    Si la imagen no tiene miniatura (subida antes de ODON-174) o su archivo
    falta, se genera desde el original y se guarda. Ante dos peticiones
    simultáneas gana la primera y la otra descarta la suya."""
    if image.thumbnail_key:
        try:
            return storage.read(image.thumbnail_key)
        except StoredImageNotFound:
            logger.warning("Miniatura faltante image_id=%s; se regenera", image.id)

    thumbnail = make_thumbnail(read_image_file(storage, image))
    new_key = storage.save(image.clinic_id, thumbnail, "jpg")
    previous = image.thumbnail_key
    result = db.execute(
        update(PatientImage)
        .where(PatientImage.id == image.id)
        .where(
            PatientImage.thumbnail_key.is_(None)
            if previous is None
            else PatientImage.thumbnail_key == previous
        )
        .values(thumbnail_key=new_key)
    )
    if result.rowcount == 0:
        db.rollback()
        storage.discard(new_key)
    else:
        db.commit()
    return thumbnail


# --- Correcciones, anulación y accesos (ODON-178) -------------------------


def _ensure_can_modify(image: PatientImage, user: User) -> None:
    if user.role != Role.ADMIN.value and image.uploaded_by_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo quien subió la imagen o administración pueden modificarla.",
        )
    if image.voided_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="La imagen está anulada y no se puede modificar."
        )


def _lock(db: Session, image: PatientImage) -> PatientImage:
    """Bloquea la fila para que una corrección y una anulación no se crucen."""
    db.execute(select(PatientImage.id).where(PatientImage.id == image.id).with_for_update())
    db.refresh(image)
    return image


def _revision_conflict(current: int) -> HTTPException:
    exc = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="La imagen cambió mientras la editabas. Revisa la versión actual antes de guardar.",
    )
    exc.extra = {"current_revision": current}
    return exc


def update_metadata(
    db: Session, patient: Patient, image: PatientImage, data: PatientImageUpdate, editor: User
) -> PatientImage:
    """Corrige los metadatos con base_revision. El archivo no cambia."""
    image = _lock(db, image)
    _ensure_can_modify(image, editor)
    # La consulta solo se valida si cambia: una foto puede conservar la consulta
    # a la que ya estaba ligada aunque esa consulta se haya anulado después.
    new_visit = data.clinical_visit_id if data.clinical_visit_id != image.clinical_visit_id else None
    _validate_context(db, patient, new_visit, data.tooth, action="modificar imágenes")
    if data.base_revision != image.revision:
        current = image.revision
        db.rollback()
        raise _revision_conflict(current)
    _validate_metadata(db, patient, data.origin, data.view, data.taken_on)

    changed = [field for field in IMAGE_METADATA_FIELDS if getattr(image, field) != getattr(data, field)]
    if not changed:
        db.rollback()
        return get_image(db, patient.id, image.id)

    for field in changed:
        setattr(image, field, getattr(data, field))
    image.revision += 1
    _add_revision(db, image, editor)
    try:
        db.flush()
        audit_service.record(
            db, editor, "image.updated", "image", image.id,
            patient_id=patient.id, fields=changed, clinic_id=patient.clinic_id,
            detail=f"revision={image.revision} fields={','.join(sorted(changed))}",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Solo el choque de número de revisión es una edición simultánea;
        # cualquier otra violación es un error real y no debe disfrazarse de 409.
        if "uq_image_revisions_image_revision" not in str(exc.orig):
            raise
        raise _revision_conflict(get_image(db, patient.id, image.id).revision)

    return get_image(db, patient.id, image.id)


def void_image(db: Session, patient: Patient, image: PatientImage, reason: str, user: User) -> PatientImage:
    """Anula una foto errónea con motivo. Se conserva y el listado la sigue
    devolviendo con voided_at; la galería la oculta salvo que se pida verla."""
    image = _lock(db, image)
    _ensure_can_modify(image, user)
    if patient.archived_at is not None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para modificar imágenes.",
        )
    image.voided_at = datetime.now(timezone.utc)
    image.voided_by_user_id = user.id
    image.void_reason = reason
    # El motivo no se guarda en la auditoría: solo el nombre del campo.
    audit_service.record(
        db, user, "image.voided", "image", image.id,
        patient_id=patient.id, fields=["void_reason", "voided_at"], clinic_id=patient.clinic_id,
    )
    db.commit()

    return get_image(db, patient.id, image.id)


def list_revisions(db: Session, image: PatientImage) -> list[dict]:
    revisions = (
        db.query(PatientImageRevision)
        .options(joinedload(PatientImageRevision.edited_by))
        .filter(PatientImageRevision.image_id == image.id)
        .order_by(PatientImageRevision.revision.desc())
        .all()
    )
    return [
        {
            **{field: getattr(r, field) for field in IMAGE_METADATA_FIELDS},
            "revision": r.revision,
            "edited_by": {"id": r.edited_by.id, "name": r.edited_by.name},
            "edited_at": r.edited_at,
        }
        for r in revisions
    ]


def record_access(db: Session, image: PatientImage, user: User) -> None:
    """Registra la apertura del original (las miniaturas no se registran)."""
    db.add(ImageAccessLog(clinic_id=image.clinic_id, image_id=image.id, user_id=user.id))
    db.commit()


def list_access(db: Session, image: PatientImage) -> list[dict]:
    logs = (
        db.query(ImageAccessLog)
        .options(joinedload(ImageAccessLog.user))
        .filter(ImageAccessLog.image_id == image.id)
        .order_by(ImageAccessLog.accessed_at.desc(), ImageAccessLog.id.desc())
        .all()
    )
    return [{"user": {"id": log.user.id, "name": log.user.name}, "accessed_at": log.accessed_at} for log in logs]
