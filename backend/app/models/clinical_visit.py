from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base

# Contenido clínico de una consulta: se copia en cada revisión.
VISIT_CONTENT_FIELDS = (
    "visit_at",
    "doctor_id",
    "reason",
    "findings",
    "diagnosis",
    "procedures",
    "instructions",
    "next_visit_date",
)


class ClinicalVisit(Base):
    """Consulta clínica de un paciente (ODON-154).

    Guarda el contenido vigente. Cada guardado (alta o edición) agrega una
    revisión en clinical_visit_revisions con su autor y fecha. Una consulta
    no se borra: se anula con motivo y queda visible."""

    __tablename__ = "clinical_visits"
    __table_args__ = (
        UniqueConstraint("id", "clinic_id", name="uq_clinical_visits_id_clinic"),
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_clinical_visits_patient_clinic",
        ),
        ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_clinical_visits_doctor_clinic",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_clinical_visits_author_clinic",
        ),
        CheckConstraint("revision >= 1", name="ck_clinical_visits_revision"),
        # Anulada: fecha, autor y motivo van juntos.
        CheckConstraint(
            "(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR "
            "(voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_clinical_visits_void",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    visit_at = Column(DateTime(timezone=True), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    reason = Column(Text, nullable=False)
    findings = Column(Text)
    diagnosis = Column(Text)
    procedures = Column(Text)
    instructions = Column(Text)
    next_visit_date = Column(Date)

    revision = Column(Integer, nullable=False, server_default="1")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    voided_at = Column(DateTime(timezone=True))
    voided_by_user_id = Column(Integer, ForeignKey("users.id"))
    void_reason = Column(Text)

    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    voided_by = relationship("User", foreign_keys=[voided_by_user_id])
    revisions = relationship(
        "ClinicalVisitRevision",
        back_populates="visit",
        order_by="ClinicalVisitRevision.revision",
        foreign_keys="ClinicalVisitRevision.visit_id",
        passive_deletes="all",
    )


class ClinicalVisitRevision(Base):
    """Copia del contenido de una consulta en cada guardado, con su autor.

    La revisión 1 es el alta. Ninguna revisión se modifica ni se borra."""

    __tablename__ = "clinical_visit_revisions"
    __table_args__ = (
        UniqueConstraint("visit_id", "revision", name="uq_clinical_visit_revision"),
        ForeignKeyConstraint(
            ["visit_id", "clinic_id"],
            ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_visit_revisions_visit_clinic",
        ),
        ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_visit_revisions_doctor_clinic",
        ),
        ForeignKeyConstraint(
            ["edited_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_visit_revisions_editor_clinic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("clinical_visits.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    edited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    visit_at = Column(DateTime(timezone=True), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    reason = Column(Text, nullable=False)
    findings = Column(Text)
    diagnosis = Column(Text)
    procedures = Column(Text)
    instructions = Column(Text)
    next_visit_date = Column(Date)

    visit = relationship("ClinicalVisit", back_populates="revisions", foreign_keys=[visit_id])
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    edited_by = relationship("User", foreign_keys=[edited_by_user_id])

