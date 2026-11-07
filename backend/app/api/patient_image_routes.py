"""Imágenes clínicas del paciente (ODON-8).

Los archivos solo se entregan por aquí: sin carpeta estática ni URL pública,
con la clínica tomada del token. Administración y doctores; Recepción no
accede (docs/PERMISSIONS.md). Subir exige consentimiento vigente
(ODON-170); la galería usa el listado y las miniaturas (ODON-174). Los
metadatos se corrigen con revisiones, una foto errónea se anula y cada
apertura del original queda registrada (ODON-178).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.patient_image import IMAGE_TYPES, image_max_bytes
from app.models.user import User
from app.schemas.patient_image_schema import (
    ImageAccessResponse,
    ImageVoid,
    PatientImageResponse,
    PatientImageRevisionResponse,
    PatientImageUpdate,
)
from app.services import patient_image_service as service
from app.services.image_storage import ImageStorage, get_image_storage

clinical_user = require_roles(Role.ADMIN, Role.DOCTOR)
admin_user = require_roles(Role.ADMIN)

router = APIRouter(
    prefix="/patients/{patient_id}/images",
    tags=["Images"],
    dependencies=[Depends(clinical_user)],
)


_PRIVATE_FILE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
_BINARY = {"schema": {"type": "string", "format": "binary"}}


@router.get("", response_model=list[PatientImageResponse])
def list_images(patient_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    """Imágenes del paciente, la más reciente primero (solo metadatos)."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return [service.to_response(image) for image in service.list_images(db, patient_id)]


@router.post("", response_model=PatientImageResponse, status_code=status.HTTP_201_CREATED)
def upload_image(
    patient_id: int,
    file: UploadFile = File(..., description="JPEG, PNG o WebP; se valida por contenido"),
    clinical_visit_id: Optional[int] = Form(None),
    tooth: Optional[int] = Form(None, description="Pieza dental FDI"),
    origin: Optional[str] = Form(None, description="intraoral_camera, phone, camera o external (obligatorio)"),
    view: Optional[str] = Form(None, description="Tipo de vista (opcional)"),
    taken_on: Optional[date] = Form(None, description="Fecha de toma (opcional, no futura)"),
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
    storage: ImageStorage = Depends(get_image_storage),
):
    """Sube una fotografía clínica. Se recodifica sin metadatos (EXIF, GPS)."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    # Un byte más que el máximo basta para saber si lo supera.
    raw = file.file.read(image_max_bytes() + 1)
    image = service.upload_image(
        db,
        storage,
        patient,
        raw,
        file.filename or "",
        user,
        clinical_visit_id=clinical_visit_id,
        tooth=tooth,
        origin=origin or None,
        view=view or None,
        taken_on=taken_on,
    )
    return service.to_response(image)


@router.get("/{image_id}", response_model=PatientImageResponse)
def get_image(patient_id: int, image_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(service.get_image(db, patient_id, image_id))


@router.patch("/{image_id}", response_model=PatientImageResponse)
def update_image(
    patient_id: int,
    image_id: int,
    data: PatientImageUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Corrige los metadatos (con base_revision). Solo quien la subió o administración."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    image = service.get_image(db, patient_id, image_id)
    return service.to_response(service.update_metadata(db, patient, image, data, user))


@router.post("/{image_id}/void", response_model=PatientImageResponse)
def void_image(
    patient_id: int,
    image_id: int,
    data: ImageVoid,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
):
    """Anula una foto errónea con motivo. Se conserva y se puede consultar."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    image = service.get_image(db, patient_id, image_id)
    return service.to_response(service.void_image(db, patient, image, data.reason, user))


@router.get("/{image_id}/revisions", response_model=list[PatientImageRevisionResponse])
def list_image_revisions(
    patient_id: int, image_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)
):
    """Historial de metadatos, la revisión más reciente primero (la 1 es el alta)."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.list_revisions(db, service.get_image(db, patient_id, image_id))


@router.get("/{image_id}/access-log", response_model=list[ImageAccessResponse])
def list_image_access(
    patient_id: int, image_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)
):
    """Quién abrió el original y cuándo. Solo administración."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.list_access(db, service.get_image(db, patient_id, image_id))


@router.get(
    "/{image_id}/thumbnail",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": _BINARY}, "description": "Miniatura JPEG (lado mayor 320 px)"}},
)
def get_image_thumbnail(
    patient_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
    storage: ImageStorage = Depends(get_image_storage),
):
    """Miniatura para la galería; se genera si la imagen no tenía."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    image = service.get_image(db, patient_id, image_id)
    content = service.read_thumbnail(db, storage, image)
    return Response(content=content, media_type="image/jpeg", headers=_PRIVATE_FILE_HEADERS)


@router.get(
    "/{image_id}/file",
    response_class=Response,
    responses={200: {"content": {t: _BINARY for t in IMAGE_TYPES}, "description": "Archivo de la imagen"}},
)
def get_image_file(
    patient_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
    storage: ImageStorage = Depends(get_image_storage),
):
    """Contenido de la imagen. No se guarda en cachés compartidas y cada apertura queda registrada."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    image = service.get_image(db, patient_id, image_id)
    content = service.read_image_file(storage, image)
    extension = IMAGE_TYPES[image.content_type]
    service.record_access(db, image, user)
    return Response(
        content=content,
        media_type=image.content_type,
        headers={
            **_PRIVATE_FILE_HEADERS,
            "Content-Disposition": f'inline; filename="imagen-{image.id}.{extension}"',
        },
    )
