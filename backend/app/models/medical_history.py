from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database.connection import Base

# Condiciones médicas de la historia (ODON-150). Cada una guarda
# {"present": true/false/null, "detail": texto o null}; null = sin dato.
MEDICAL_CONDITIONS = (
    "diabetes",
    "hypertension",
    "heart_disease",
    "bleeding_disorder",
    "respiratory_disease",
    "liver_kidney_disease",
    "immunosuppression",
    "pregnancy_lactation",
)

SMOKING_STATUSES = ("never", "former", "current")


class PatientMedicalHistory(Base):
    """Una versión de la historia médica y odontológica de un paciente.

    Cada guardado crea una versión nueva (1, 2, 3...) con su autor y fecha;
    ninguna se modifica ni se borra. La vigente es la de mayor versión."""

    __tablename__ = "patient_medical_histories"
    __table_args__ = (
        UniqueConstraint("patient_id", "version", name="uq_medical_history_patient_version"),
        # Paciente y autor son de la misma clínica que la historia.
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_medical_history_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_medical_history_author_clinic",
        ),
        CheckConstraint("version >= 1", name="ck_medical_history_version"),
        CheckConstraint(
            "smoking_status IN ('never', 'former', 'current')", name="ck_medical_history_smoking"
        ),
        CheckConstraint(
            "cigarettes_per_day BETWEEN 1 AND 200", name="ck_medical_history_cigarettes"
        ),
        CheckConstraint("brushing_per_day BETWEEN 0 AND 10", name="ck_medical_history_brushing"),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Antecedentes médicos
    conditions = Column(JSONB, nullable=False, server_default="{}")
    other_conditions = Column(Text)
    allergies = Column(Text)
    current_medications = Column(Text)

    # Hábitos
    smoking_status = Column(String(10))
    cigarettes_per_day = Column(SmallInteger)
    alcohol = Column(Boolean)
    alcohol_detail = Column(Text)
    bruxism = Column(Boolean)

    # Antecedentes odontológicos
    chief_complaint = Column(Text)
    last_dental_visit = Column(String(80))
    previous_treatments = Column(Text)
    brushing_per_day = Column(SmallInteger)
    uses_floss = Column(Boolean)
    gum_bleeding = Column(Boolean)

    notes = Column(Text)

    created_by = relationship("User", foreign_keys=[created_by_user_id])
