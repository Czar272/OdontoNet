"""patient medical histories

Revision ID: b5d9e2f4c731
Revises: a8c3e5f7b192
Create Date: 2026-11-02 22:00:00

Historia médica y odontológica del paciente (ODON-150):
- patient_medical_histories: una fila por versión. Cada guardado crea una
  versión nueva con autor y fecha; las anteriores no se modifican.
- FKs compuestas para que paciente y autor sean de la clínica de la historia.
- conditions (JSONB): condiciones médicas de una lista fija, cada una con
  present (sí/no/sin dato) y detalle.

Solo crea una tabla nueva: no modifica ni borra datos. El downgrade se
detiene si ya hay historias registradas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b5d9e2f4c731"
down_revision: Union[str, Sequence[str], None] = "a8c3e5f7b192"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_medical_histories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("other_conditions", sa.Text(), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("current_medications", sa.Text(), nullable=True),
        sa.Column("smoking_status", sa.String(length=10), nullable=True),
        sa.Column("cigarettes_per_day", sa.SmallInteger(), nullable=True),
        sa.Column("alcohol", sa.Boolean(), nullable=True),
        sa.Column("alcohol_detail", sa.Text(), nullable=True),
        sa.Column("bruxism", sa.Boolean(), nullable=True),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("last_dental_visit", sa.String(length=80), nullable=True),
        sa.Column("previous_treatments", sa.Text(), nullable=True),
        sa.Column("brushing_per_day", sa.SmallInteger(), nullable=True),
        sa.Column("uses_floss", sa.Boolean(), nullable=True),
        sa.Column("gum_bleeding", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_medical_history_version"),
        sa.CheckConstraint("smoking_status IN ('never', 'former', 'current')", name="ck_medical_history_smoking"),
        sa.CheckConstraint("cigarettes_per_day BETWEEN 1 AND 200", name="ck_medical_history_cigarettes"),
        sa.CheckConstraint("brushing_per_day BETWEEN 0 AND 10", name="ck_medical_history_brushing"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_medical_history_patient_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id", "clinic_id"],
            ["users.id", "users.clinic_id"],
            name="fk_medical_history_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "version", name="uq_medical_history_patient_version"),
    )
    op.create_index(op.f("ix_patient_medical_histories_id"), "patient_medical_histories", ["id"])
    op.create_index(op.f("ix_patient_medical_histories_patient_id"), "patient_medical_histories", ["patient_id"])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM patient_medical_histories")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} versiones de historias médicas registradas. Revertir esta migración las borraría; "
            "respáldalas y elimínalas a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_patient_medical_histories_patient_id"), table_name="patient_medical_histories")
    op.drop_index(op.f("ix_patient_medical_histories_id"), table_name="patient_medical_histories")
    op.drop_table("patient_medical_histories")
