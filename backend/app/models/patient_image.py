import os

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base
from app.models.treatment import TOOTH_CHECK

# Tipos aceptados y extensión con la que se guardan (ODON-8).
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_TYPE_VALUES = ", ".join(f"'{t}'" for t in IMAGE_TYPES)


def image_max_bytes() -> int:
    """Tamaño máximo por imagen; IMAGE_MAX_MB, 10 MB por defecto."""
    return int(float(os.getenv("IMAGE_MAX_MB", "10")) * 1024 * 1024)


class PatientImage(Base):
    """Fotografía clínica de un paciente (ODON-166).

    El archivo vive en el almacenamiento privado (storage_key); aquí quedan la
    clínica, el paciente, la consulta y la pieza opcionales, el autor y la
    huella SHA-256 para verificar respaldos. No se borra."""

    __tablename__ = "patient_images"
    __table_args__ = (
        UniqueConstraint("id", "clinic_id", name="uq_patient_images_id_clinic"),
        UniqueConstraint("storage_key", name="uq_patient_images_storage_key"),
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
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    clinical_visit_id = Column(Integer, ForeignKey("clinical_visits.id"))
    tooth = Column(SmallInteger)

    storage_key = Column(String(80), nullable=False)
    content_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    clinical_visit = relationship("ClinicalVisit", foreign_keys=[clinical_visit_id])
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
