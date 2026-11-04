"""Imágenes clínicas del paciente (ODON-8).

Los archivos solo se entregan por aquí: sin carpeta estática ni URL pública,
con la clínica tomada del token. Administración y doctores; Recepción no
accede (docs/PERMISSIONS.md). Subir exige consentimiento vigente
(ODON-170); la galería llega en ODON-174.
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


@router.get(
    "/{image_id}/file",
    response_class=Response,
    responses={
        200: {
            "content": {t: {"schema": {"type": "string", "format": "binary"}} for t in IMAGE_TYPES},
            "description": "Archivo de la imagen",
        }
    },
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
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="imagen-{image.id}.{extension}"',
        },
    )
