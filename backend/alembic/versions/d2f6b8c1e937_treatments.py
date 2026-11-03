"""treatments

Revision ID: d2f6b8c1e937
Revises: c7e1a4b8d520
Create Date: 2026-11-03 08:00:00

Plan de tratamiento y seguimiento (ODON-158):
- treatments: tratamientos del paciente con procedimiento, pieza dental FDI
  opcional, estado (proposed, accepted, in_progress, completed, cancelled),
  fecha estimada, consulta en que se propuso (opcional) y consulta en que se
  realizó (obligatoria al completar).
- treatment_status_changes: historial de estados con autor, fecha y motivo.
- FKs compuestas para que paciente, consultas y autores sean de la clínica.

Solo crea tablas nuevas: no modifica ni borra datos. El downgrade se detiene
si ya hay tratamientos registrados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2f6b8c1e937"
down_revision: Union[str, Sequence[str], None] = "c7e1a4b8d520"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = "'proposed', 'accepted', 'in_progress', 'completed', 'cancelled'"
TOOTH_CHECK = (
    "tooth IS NULL OR "
    "(tooth / 10 BETWEEN 1 AND 4 AND tooth % 10 BETWEEN 1 AND 8) OR "
    "(tooth / 10 BETWEEN 5 AND 8 AND tooth % 10 BETWEEN 1 AND 5)"
)


def upgrade() -> None:
    op.create_table(
        "treatments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("procedure", sa.String(length=300), nullable=False),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="proposed", nullable=False),
        sa.Column("proposed_visit_id", sa.Integer(), nullable=True),
        sa.Column("completed_visit_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_treatments_status"),
        sa.CheckConstraint(TOOTH_CHECK, name="ck_treatments_tooth"),
        sa.CheckConstraint(
            "status <> 'completed' OR completed_visit_id IS NOT NULL", name="ck_treatments_completed_visit"
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["proposed_visit_id"], ["clinical_visits.id"]),
        sa.ForeignKeyConstraint(["completed_visit_id"], ["clinical_visits.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["patient_id", "clinic_id"], ["patients.id", "patients.clinic_id"],
            name="fk_treatments_patient_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_visit_id", "clinic_id"], ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_treatments_proposed_visit_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["completed_visit_id", "clinic_id"], ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_treatments_completed_visit_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_treatments_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "clinic_id", name="uq_treatments_id_clinic"),
    )
    op.create_index(op.f("ix_treatments_id"), "treatments", ["id"])
    op.create_index(op.f("ix_treatments_patient_id"), "treatments", ["patient_id"])

    op.create_table(
        "treatment_status_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("treatment_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"to_status IN ({STATUSES})", name="ck_treatment_changes_to_status"),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({STATUSES})", name="ck_treatment_changes_from_status"
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["treatment_id"], ["treatments.id"]),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["treatment_id", "clinic_id"], ["treatments.id", "treatments.clinic_id"],
            name="fk_treatment_changes_treatment_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_treatment_changes_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_treatment_status_changes_id"), "treatment_status_changes", ["id"])
    op.create_index(op.f("ix_treatment_status_changes_treatment_id"), "treatment_status_changes", ["treatment_id"])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM treatments")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} tratamientos registrados. Revertir esta migración los borraría; "
            "respáldalos y elimínalos a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_treatment_status_changes_treatment_id"), table_name="treatment_status_changes")
    op.drop_index(op.f("ix_treatment_status_changes_id"), table_name="treatment_status_changes")
    op.drop_table("treatment_status_changes")
    op.drop_index(op.f("ix_treatments_patient_id"), table_name="treatments")
    op.drop_index(op.f("ix_treatments_id"), table_name="treatments")
    op.drop_table("treatments")
