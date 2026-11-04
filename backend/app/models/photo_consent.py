from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


class PatientPhotoConsent(Base):
    """Consentimiento del paciente para fotografías clínicas (ODON-170).

    Una fila por versión, nunca se modifica ni se borra; la vigente es la de
    mayor versión. Revocar es registrar una versión con granted = false.

    research_use solo deja constancia de lo que dice el formulario firmado:
    las condiciones de uso en investigación las fija el protocolo vigente del
    comité de ética, no el sistema."""

    __tablename__ = "patient_photo_consents"
    __table_args__ = (
        UniqueConstraint("patient_id", "version", name="uq_photo_consents_patient_version"),
        UniqueConstraint("id", "patient_id", "clinic_id", name="uq_photo_consents_id_patient_clinic"),
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_photo_consents_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["recorded_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_photo_consents_author_clinic",
        ),
        CheckConstraint("version > 0", name="ck_photo_consents_version"),
        # Sin autorización clínica no puede haber uso en investigación.
        CheckConstraint("granted OR NOT research_use", name="ck_photo_consents_research_requires_grant"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)

    granted = Column(Boolean, nullable=False)
    research_use = Column(Boolean, nullable=False, server_default=text("false"))
    # Fecha del documento: firma o revocación.
    signed_on = Column(Date, nullable=False)
    notes = Column(String(500))

    recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    recorded_by = relationship("User", foreign_keys=[recorded_by_user_id])
