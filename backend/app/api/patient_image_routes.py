"""Imágenes clínicas del paciente (ODON-8).

Los archivos solo se entregan por aquí: sin carpeta estática ni URL pública,
con la clínica tomada del token. Administración y doctores; Recepción no
accede (docs/PERMISSIONS.md). La subida llega en ODON-170 y la galería en
ODON-174.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.permissions import Role, require_roles
from app.database.dependencies import get_db
from app.models.patient_image import IMAGE_TYPES
from app.models.user import User
from app.services import patient_image_service as service
from app.services.image_storage import ImageStorage, get_image_storage

clinical_user = require_roles(Role.ADMIN, Role.DOCTOR)

router = APIRouter(
    prefix="/patients/{patient_id}/images",
    tags=["Images"],
    dependencies=[Depends(clinical_user)],
)


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
