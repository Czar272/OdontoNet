"""clinical visits

Revision ID: c7e1a4b8d520
Revises: b5d9e2f4c731
Create Date: 2026-11-02 23:45:00

Consultas clínicas (ODON-154):
- clinical_visits: contenido vigente de cada consulta, revisión actual y
  anulación (fecha, autor y motivo). Una consulta no se borra.
- clinical_visit_revisions: copia del contenido en cada guardado, con autor
  y fecha; la revisión 1 es el alta.
- FKs compuestas para que paciente, doctor, autor y revisiones sean de la
  clínica de la consulta.

Solo crea tablas nuevas: no modifica ni borra datos. El downgrade se detiene
si ya hay consultas registradas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7e1a4b8d520"
down_revision: Union[str, Sequence[str], None] = "b5d9e2f4c731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _content_columns():
    return [
        sa.Column("visit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("procedures", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("next_visit_date", sa.Date(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "clinical_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        *_content_columns(),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("revision >= 1", name="ck_clinical_visits_revision"),
        sa.CheckConstraint(
            "(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR "
            "(voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_clinical_visits_void",
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voided_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["patient_id", "clinic_id"], ["patients.id", "patients.clinic_id"],
            name="fk_clinical_visits_patient_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id", "clinic_id"], ["doctors.id", "doctors.clinic_id"],
            name="fk_clinical_visits_doctor_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_clinical_visits_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "clinic_id", name="uq_clinical_visits_id_clinic"),
    )
    op.create_index(op.f("ix_clinical_visits_id"), "clinical_visits", ["id"])
    op.create_index(op.f("ix_clinical_visits_patient_id"), "clinical_visits", ["patient_id"])

    op.create_table(
        "clinical_visit_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("edited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *_content_columns(),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["clinical_visits.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["edited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["visit_id", "clinic_id"], ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_visit_revisions_visit_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id", "clinic_id"], ["doctors.id", "doctors.clinic_id"],
            name="fk_visit_revisions_doctor_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["edited_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_visit_revisions_editor_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("visit_id", "revision", name="uq_clinical_visit_revision"),
    )
    op.create_index(op.f("ix_clinical_visit_revisions_id"), "clinical_visit_revisions", ["id"])
    op.create_index(op.f("ix_clinical_visit_revisions_visit_id"), "clinical_visit_revisions", ["visit_id"])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM clinical_visits")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} consultas clínicas registradas. Revertir esta migración las borraría; "
            "respáldalas y elimínalas a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_clinical_visit_revisions_visit_id"), table_name="clinical_visit_revisions")
    op.drop_index(op.f("ix_clinical_visit_revisions_id"), table_name="clinical_visit_revisions")
    op.drop_table("clinical_visit_revisions")
    op.drop_index(op.f("ix_clinical_visits_patient_id"), table_name="clinical_visits")
    op.drop_index(op.f("ix_clinical_visits_id"), table_name="clinical_visits")
    op.drop_table("clinical_visits")
