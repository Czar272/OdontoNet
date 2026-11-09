
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.settings import get_settings
from app.database.connection import Base
from app.models.treatment import TOOTH_CHECK

# Tipos aceptados y extensión con la que se guardan (ODON-8).
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_TYPE_VALUES = ", ".join(f"'{t}'" for t in IMAGE_TYPES)

# Metadatos clínicos (ODON-178). Espejo de etiquetas en el frontend
# (components/patients/imageUpload.ts).
IMAGE_ORIGINS = ("intraoral_camera", "phone", "camera", "external")
IMAGE_VIEWS = ("frontal", "right_lateral", "left_lateral", "upper_occlusal", "lower_occlusal", "detail", "other")
# Campos corregibles; el archivo nunca cambia.
IMAGE_METADATA_FIELDS = ("origin", "view", "taken_on", "clinical_visit_id", "tooth")


def _in(column: str, values) -> str:
    return f"{column} IS NULL OR {column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


ORIGIN_CHECK = _in("origin", IMAGE_ORIGINS)
VIEW_CHECK = _in("view", IMAGE_VIEWS)


def image_max_bytes() -> int:
    """Tamaño máximo por imagen; IMAGE_MAX_MB, 10 MB por defecto."""
    return int(get_settings().image_max_mb * 1024 * 1024)


class PatientImage(Base):
    """Fotografía clínica de un paciente (ODON-166).

    El archivo vive en el almacenamiento privado (storage_key) y nunca cambia;
    aquí quedan la clínica, el paciente, el autor, el consentimiento vigente al
    subirla, la huella SHA-256 para verificar respaldos y los metadatos
    corregibles (origen, vista, fecha de toma, consulta y pieza), cuyo
    historial está en patient_image_revisions (la revisión 1 es el alta).
    No se borra: una foto errónea se anula con motivo (ODON-178)."""

    __tablename__ = "patient_images"
    __table_args__ = (
        UniqueConstraint("id", "clinic_id", name="uq_patient_images_id_clinic"),
        UniqueConstraint("storage_key", name="uq_patient_images_storage_key"),
        UniqueConstraint("thumbnail_key", name="uq_patient_images_thumbnail_key"),
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_patient_images_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["clinical_visit_id", "clinic_id"],
            ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_patient_images_visit_clinic",
        ),
        # El consentimiento aplicado debe ser del mismo paciente y clínica.
        ForeignKeyConstraint(
            ["consent_id", "patient_id", "clinic_id"],
            ["patient_photo_consents.id", "patient_photo_consents.patient_id", "patient_photo_consents.clinic_id"],
            name="fk_patient_images_consent",
        ),
        ForeignKeyConstraint(
            ["uploaded_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_patient_images_author_clinic",
        ),
        CheckConstraint(f"content_type IN ({_TYPE_VALUES})", name="ck_patient_images_content_type"),
        CheckConstraint("size_bytes > 0", name="ck_patient_images_size"),
        CheckConstraint("width > 0 AND height > 0", name="ck_patient_images_dimensions"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_patient_images_sha256"),
        CheckConstraint(TOOTH_CHECK, name="ck_patient_images_tooth"),
        CheckConstraint(ORIGIN_CHECK, name="ck_patient_images_origin"),
        CheckConstraint(VIEW_CHECK, name="ck_patient_images_view"),
        CheckConstraint("revision >= 1", name="ck_patient_images_revision"),
        ForeignKeyConstraint(
            ["voided_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_patient_images_voided_by_clinic",
        ),
        CheckConstraint(
            "(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR "
            "(voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_patient_images_void",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    clinical_visit_id = Column(Integer, ForeignKey("clinical_visits.id"))
    tooth = Column(SmallInteger)
    # Null en imágenes subidas antes de ODON-178 («sin registrar»).
    origin = Column(String(20))
    view = Column(String(20))
    taken_on = Column(Date)
    revision = Column(Integer, nullable=False, server_default="1")

    storage_key = Column(String(80), nullable=False)
    # Miniatura JPEG (ODON-174); se regenera desde el original si falta.
    thumbnail_key = Column(String(80))
    content_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    # Versión del consentimiento vigente al subir (ODON-170).
    consent_id = Column(Integer, ForeignKey("patient_photo_consents.id"), nullable=False)

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    voided_at = Column(DateTime(timezone=True))
    voided_by_user_id = Column(Integer, ForeignKey("users.id"))
    void_reason = Column(Text)

    clinical_visit = relationship("ClinicalVisit", foreign_keys=[clinical_visit_id])
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
    voided_by = relationship("User", foreign_keys=[voided_by_user_id])
    consent = relationship("PatientPhotoConsent", foreign_keys=[consent_id])


class PatientImageRevision(Base):
    """Copia de los metadatos de una imagen en cada guardado (ODON-178)."""

    __tablename__ = "patient_image_revisions"
    __table_args__ = (
        UniqueConstraint("image_id", "revision", name="uq_image_revisions_image_revision"),
        ForeignKeyConstraint(
            ["image_id", "clinic_id"],
            ["patient_images.id", "patient_images.clinic_id"],
            name="fk_image_revisions_image_clinic",
        ),
        ForeignKeyConstraint(
            ["edited_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_image_revisions_author_clinic",
        ),
        ForeignKeyConstraint(
            ["clinical_visit_id", "clinic_id"],
            ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_image_revisions_visit_clinic",
        ),
        CheckConstraint("revision >= 1", name="ck_image_revisions_revision"),
        CheckConstraint(ORIGIN_CHECK, name="ck_image_revisions_origin"),
        CheckConstraint(VIEW_CHECK, name="ck_image_revisions_view"),
        CheckConstraint(TOOTH_CHECK, name="ck_image_revisions_tooth"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    image_id = Column(Integer, ForeignKey("patient_images.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    origin = Column(String(20))
    view = Column(String(20))
    taken_on = Column(Date)
    clinical_visit_id = Column(Integer, ForeignKey("clinical_visits.id"))
    tooth = Column(SmallInteger)
    edited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    edited_by = relationship("User", foreign_keys=[edited_by_user_id])


class ImageAccessLog(Base):
    """Apertura del archivo original de una imagen (ODON-178).

    Solo el original: las miniaturas no se registran. Base para la auditoría
    persistente de acciones clínicas (ODON-222)."""

    __tablename__ = "image_access_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["image_id", "clinic_id"],
            ["patient_images.id", "patient_images.clinic_id"],
            name="fk_image_access_image_clinic",
        ),
        ForeignKeyConstraint(
            ["user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_image_access_user_clinic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    image_id = Column(Integer, ForeignKey("patient_images.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    accessed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
