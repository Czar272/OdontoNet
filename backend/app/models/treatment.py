from enum import Enum

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

from app.database.connection import Base


class TreatmentStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Transiciones permitidas (espejo en frontend/src/components/patients/treatmentStatus.ts).
# Completado y Cancelado son finales.
TREATMENT_TRANSITIONS = {
    TreatmentStatus.PROPOSED: {TreatmentStatus.ACCEPTED, TreatmentStatus.CANCELLED},
    TreatmentStatus.ACCEPTED: {TreatmentStatus.IN_PROGRESS, TreatmentStatus.COMPLETED, TreatmentStatus.CANCELLED},
    TreatmentStatus.IN_PROGRESS: {TreatmentStatus.COMPLETED, TreatmentStatus.CANCELLED},
    TreatmentStatus.COMPLETED: set(),
    TreatmentStatus.CANCELLED: set(),
}

_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in TreatmentStatus)

# Numeración FDI: permanentes 11–48 (cuadrantes 1–4, piezas 1–8) y temporales
# 51–85 (cuadrantes 5–8, piezas 1–5).
TOOTH_CHECK = (
    "tooth IS NULL OR "
    "(tooth / 10 BETWEEN 1 AND 4 AND tooth % 10 BETWEEN 1 AND 8) OR "
    "(tooth / 10 BETWEEN 5 AND 8 AND tooth % 10 BETWEEN 1 AND 5)"
)


def is_valid_tooth(tooth: int) -> bool:
    quadrant, piece = divmod(tooth, 10)
    return (1 <= quadrant <= 4 and 1 <= piece <= 8) or (5 <= quadrant <= 8 and 1 <= piece <= 5)


class Treatment(Base):
    """Tratamiento propuesto para un paciente (ODON-158).

    Se asocia opcionalmente a la consulta en que se propuso y, al completarse,
    obligatoriamente a la consulta en que se realizó. Cada cambio de estado
    queda en treatment_status_changes. No se borra: se cancela con motivo."""

    __tablename__ = "treatments"
    __table_args__ = (
        UniqueConstraint("id", "clinic_id", name="uq_treatments_id_clinic"),
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_treatments_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["proposed_visit_id", "clinic_id"],
            ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_treatments_proposed_visit_clinic",
        ),
        ForeignKeyConstraint(
            ["completed_visit_id", "clinic_id"],
            ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_treatments_completed_visit_clinic",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_treatments_author_clinic",
        ),
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_treatments_status"),
        CheckConstraint(TOOTH_CHECK, name="ck_treatments_tooth"),
        # Completado siempre con la consulta en que se realizó.
        CheckConstraint(
            "status <> 'completed' OR completed_visit_id IS NOT NULL",
            name="ck_treatments_completed_visit",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    procedure = Column(String(300), nullable=False)
    tooth = Column(SmallInteger)
    notes = Column(Text)
    planned_date = Column(Date)
    status = Column(String(20), nullable=False, server_default=TreatmentStatus.PROPOSED.value)

    proposed_visit_id = Column(Integer, ForeignKey("clinical_visits.id"))
    completed_visit_id = Column(Integer, ForeignKey("clinical_visits.id"))

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    proposed_visit = relationship("ClinicalVisit", foreign_keys=[proposed_visit_id])
    completed_visit = relationship("ClinicalVisit", foreign_keys=[completed_visit_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    updated_by = relationship("User", foreign_keys=[updated_by_user_id])
    status_changes = relationship(
        "TreatmentStatusChange",
        back_populates="treatment",
        order_by="TreatmentStatusChange.id",
        foreign_keys="TreatmentStatusChange.treatment_id",
        passive_deletes="all",
    )


class TreatmentStatusChange(Base):
    """Historial de estados de un tratamiento. El primero (from_status NULL) es el alta."""

    __tablename__ = "treatment_status_changes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["treatment_id", "clinic_id"],
            ["treatments.id", "treatments.clinic_id"],
            name="fk_treatment_changes_treatment_clinic",
        ),
        ForeignKeyConstraint(
            ["changed_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_treatment_changes_author_clinic",
        ),
        CheckConstraint(f"to_status IN ({_STATUS_VALUES})", name="ck_treatment_changes_to_status"),
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({_STATUS_VALUES})",
            name="ck_treatment_changes_from_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    treatment_id = Column(Integer, ForeignKey("treatments.id"), nullable=False, index=True)
    from_status = Column(String(20))
    to_status = Column(String(20), nullable=False)
    reason = Column(Text)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    treatment = relationship("Treatment", back_populates="status_changes", foreign_keys=[treatment_id])
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])
