"""Imágenes clínicas del paciente (ODON-166).

Guarda el archivo en el almacenamiento privado y su registro en la base como
una sola operación: si la base falla, el archivo recién escrito se descarta.
Las imágenes no se borran.
"""
import hashlib
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinical_visit import ClinicalVisit
from app.models.patient import Patient
from app.models.patient_image import IMAGE_TYPES, PatientImage, image_max_bytes
from app.models.treatment import is_valid_tooth
from app.models.user import User
from app.services.image_storage import ImageStorage, StoredImageNotFound

audit_logger = logging.getLogger("odontonet.audit")
logger = logging.getLogger(__name__)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def get_clinic_patient(db: Session, patient_id: int, clinic_id: int) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id, Patient.clinic_id == clinic_id).first()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")
    return patient


def get_image(db: Session, patient_id: int, image_id: int) -> PatientImage:
    image = (
        db.query(PatientImage)
        .filter(PatientImage.id == image_id, PatientImage.patient_id == patient_id)
        .first()
    )
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    return image


def _validate(db: Session, patient: Patient, data: bytes, content_type: str, visit_id, tooth) -> None:
    if patient.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente está archivado. Reactívalo para agregar imágenes.",
        )
    if content_type not in IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo de imagen no permitido. Usa JPEG, PNG o WebP.",
        )
    if not data:
        raise _unprocessable("La imagen está vacía.")
    max_bytes = image_max_bytes()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"La imagen supera el máximo de {max_bytes // (1024 * 1024)} MB.",
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
    clinical_visit_id: Optional[int] = None,
    tooth: Optional[int] = None,
) -> PatientImage:
    """Valida, guarda el archivo y registra la imagen.

    El tipo y las dimensiones los determina quien llama a partir del contenido
    real del archivo (ODON-170), no de lo que declare el cliente."""
    _validate(db, patient, data, content_type, clinical_visit_id, tooth)

    key = storage.save(patient.clinic_id, data, IMAGE_TYPES[content_type])
    image = PatientImage(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        clinical_visit_id=clinical_visit_id,
        tooth=tooth,
        storage_key=key,
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_user_id=author.id,
    )
    try:
        db.add(image)
        db.commit()
    except Exception:
        db.rollback()
        storage.discard(key)
        raise
    db.refresh(image)

    audit_logger.info(
        "image.stored image_id=%s patient_id=%s user_id=%s clinic_id=%s bytes=%s",
        image.id, patient.id, author.id, patient.clinic_id, image.size_bytes,
    )
    return image


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
