"""Imágenes clínicas del paciente (ODON-166, ODON-170).

Guarda el archivo en el almacenamiento privado y su registro en la base como
una sola operación: si la base falla, el archivo recién escrito se descarta.
Subir exige un consentimiento vigente y pasa por el saneamiento de
image_processing. Las imágenes no se borran.
"""
import hashlib
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session, joinedload

from app.models.clinical_visit import ClinicalVisit
from app.models.patient import Patient
from app.models.patient_image import IMAGE_TYPES, PatientImage, image_max_bytes
from app.models.treatment import is_valid_tooth
from app.models.user import User
from app.services.image_processing import make_thumbnail, sanitize_image
from app.services.image_storage import ImageStorage, StoredImageNotFound
from app.services.photo_consent_service import require_active_consent

audit_logger = logging.getLogger("odontonet.audit")
logger = logging.getLogger(__name__)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def _images(db: Session):
    return db.query(PatientImage).options(
        joinedload(PatientImage.clinical_visit), joinedload(PatientImage.uploaded_by)
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
        "content_type": image.content_type,
        "size_bytes": image.size_bytes,
        "width": image.width,
        "height": image.height,
        "consent_id": image.consent_id,
        "uploaded_by": {"id": image.uploaded_by.id, "name": image.uploaded_by.name},
        "uploaded_at": image.uploaded_at,
    }


def check_size(data: bytes) -> None:
    if not data:
        raise _unprocessable("La imagen está vacía.")
    max_bytes = image_max_bytes()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"La imagen supera el máximo de {max_bytes // (1024 * 1024)} MB.",
        )


def _validate_context(db: Session, patient: Patient, visit_id, tooth) -> None:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para agregar imágenes.",
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
        db.commit()
    except Exception:
        db.rollback()
        for saved in keys:
            storage.discard(saved)
        raise
    db.refresh(image)

    audit_logger.info(
        "image.stored image_id=%s patient_id=%s user_id=%s clinic_id=%s bytes=%s",
        image.id, patient.id, author.id, patient.clinic_id, image.size_bytes,
    )
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
) -> PatientImage:
    """Subida desde la API: contexto, consentimiento, tamaño y saneamiento.

    Las validaciones baratas van antes de abrir la imagen con Pillow."""
    _validate_context(db, patient, clinical_visit_id, tooth)
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
