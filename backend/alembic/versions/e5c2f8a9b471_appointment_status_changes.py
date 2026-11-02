"""appointment status changes

Revision ID: e5c2f8a9b471
Revises: d7a3b9e15c42
Create Date: 2026-11-02 12:30:00

Seguimiento de estados de citas (ODON-146 / ODON-147):
- uq_appointments_id_clinic: permite la FK compuesta (appointment_id, clinic_id);
- tabla appointment_status_changes: cada cambio de estado con estado
  anterior (vacío al crear la cita), nuevo estado, nota opcional
  («Confirmó por teléfono»), usuario y fecha. Es historial: no se edita ni se
  borra desde la API.

Es una tabla nueva: no modifica ni borra datos. Las citas existentes no
tienen historial previo; empieza a registrarse desde esta versión. El
downgrade se detiene si ya hay cambios registrados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5c2f8a9b471"
down_revision: Union[str, Sequence[str], None] = "d7a3b9e15c42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUSES = "('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')"


def upgrade() -> None:
    op.create_unique_constraint("uq_appointments_id_clinic", "appointments", ["id", "clinic_id"])

    op.create_table(
        "appointment_status_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN {_STATUSES}",
            name="ck_appointment_status_changes_from",
        ),
        sa.CheckConstraint(f"to_status IN {_STATUSES}", name="ck_appointment_status_changes_to"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["appointment_id", "clinic_id"],
            ["appointments.id", "appointments.clinic_id"],
            name="fk_appointment_status_changes_appointment_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_appointment_status_changes_id"), "appointment_status_changes", ["id"])
    op.create_index(
        op.f("ix_appointment_status_changes_appointment_id"),
        "appointment_status_changes",
        ["appointment_id"],
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM appointment_status_changes")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} cambios de estado registrados. Revertir esta migración borraría "
            "el historial; respáldalo y elimínalo a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_appointment_status_changes_appointment_id"), table_name="appointment_status_changes")
    op.drop_index(op.f("ix_appointment_status_changes_id"), table_name="appointment_status_changes")
    op.drop_table("appointment_status_changes")
    op.drop_constraint("uq_appointments_id_clinic", "appointments", type_="unique")
