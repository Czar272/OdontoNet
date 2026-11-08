from sqlalchemy import Column, DateTime, ForeignKeyConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from app.database.connection import Base


class AuditEvent(Base):
    """Auditoría persistente de cambios y exportaciones (ODON-222).

    Solo se agrega: un trigger de PostgreSQL rechaza UPDATE y DELETE (las
    pruebas pueden vaciarla con odontonet.allow_audit_purge). Cada fila guarda
    el SHA-256 de su contenido encadenado con el de la fila anterior de la misma
    clínica, así una alteración directa en la base se detecta
    (scripts/verify_audit.py). Solo ids y nombres de campo: nunca valores,
    contraseñas, tokens ni datos personales. No registra lecturas (decisión del
    desarrollador).
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["actor_user_id", "clinic_id"], ["users.id", "users.clinic_id"], name="fk_audit_events_actor_clinic"
        ),
        ForeignKeyConstraint(["clinic_id"], ["clinics.id"], name="fk_audit_events_clinic"),
        ForeignKeyConstraint(
            ["patient_id", "clinic_id"], ["patients.id", "patients.clinic_id"], name="fk_audit_events_patient_clinic"
        ),
        Index("ix_audit_events_clinic_id", "clinic_id", "id"),
        Index("ix_audit_events_clinic_actor", "clinic_id", "actor_user_id", "id"),
        Index("ix_audit_events_clinic_occurred", "clinic_id", "occurred_at"),
    )

    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, nullable=False)
    actor_user_id = Column(Integer, nullable=False)
    actor_role = Column(String(20), nullable=False)
    # p. ej. "patient.updated", "report.exported"
    action = Column(String(60), nullable=False)
    entity_type = Column(String(40), nullable=False)
    entity_id = Column(Integer)
    # Paciente afectado, si lo hay (solo el id), para filtrar sin unir tablas.
    patient_id = Column(Integer)
    # Nombres de los campos cambiados (nunca sus valores).
    fields = Column(JSONB)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    prev_hash = Column(String(64))
    hash = Column(String(64), nullable=False)
