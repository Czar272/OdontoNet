"""Imágenes clínicas del paciente (ODON-8).

Los archivos solo se entregan por aquí: sin carpeta estática ni URL pública,
con la clínica tomada del token. Administración y doctores; Recepción no
accede (docs/PERMISSIONS.md). Subir exige consentimiento vigente
(ODON-170); la galería usa el listado y las miniaturas (ODON-174).
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.patient_image import IMAGE_TYPES, image_max_bytes
from app.models.user import User
from app.schemas.patient_image_schema import PatientImageResponse
from app.services import patient_image_service as service
from app.services.image_storage import ImageStorage, get_image_storage

clinical_user = require_roles(Role.ADMIN, Role.DOCTOR)

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
    db: Session = Depends(get_db),
    user: User = Depends(clinical_user),
    storage: ImageStorage = Depends(get_image_storage),
):
    """Sube una fotografía clínica. Se recodifica sin metadatos (EXIF, GPS)."""
    patient = service.get_clinic_patient(db, patient_id, user.clinic_id)
    # Un byte más que el máximo basta para saber si lo supera.
    raw = file.file.read(image_max_bytes() + 1)
    image = service.upload_image(
        db, storage, patient, raw, file.filename or "", user, clinical_visit_id=clinical_visit_id, tooth=tooth
    )
    return service.to_response(image)


@router.get("/{image_id}", response_model=PatientImageResponse)
def get_image(patient_id: int, image_id: int, db: Session = Depends(get_db), user: User = Depends(clinical_user)):
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    return service.to_response(service.get_image(db, patient_id, image_id))


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
    """Contenido de la imagen. No se guarda en cachés compartidas."""
    service.get_clinic_patient(db, patient_id, user.clinic_id)
    image = service.get_image(db, patient_id, image_id)
    content = service.read_image_file(storage, image)
    extension = IMAGE_TYPES[image.content_type]
    return Response(
        content=content,
        media_type=image.content_type,
        headers={
            **_PRIVATE_FILE_HEADERS,
            "Content-Disposition": f'inline; filename="imagen-{image.id}.{extension}"',
        },
    )
