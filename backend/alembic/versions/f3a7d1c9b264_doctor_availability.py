"""doctor availability

Revision ID: f3a7d1c9b264
Revises: e5c2f8a9b471
Create Date: 2026-11-02 14:00:00

Disponibilidad de doctores (ODON-142 / ODON-143):
- clinics.timezone: zona horaria IANA de la clínica, America/Guatemala por
  defecto. Los horarios se escriben en la hora local de la clínica;
- doctor_availability_blocks: horario semanal por doctor, con uno o más
  bloques por día (weekday 0 = lunes … 6 = domingo, como en Python) entre
  start_time y end_time. FK compuesta para que el doctor sea de la clínica.

Solo agrega una columna con valor por defecto y una tabla nueva: no modifica
ni borra datos. Los doctores empiezan sin horario (se agenda libremente). El
downgrade se detiene si ya hay horarios registrados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f3a7d1c9b264"
down_revision: Union[str, Sequence[str], None] = "e5c2f8a9b471"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clinics",
        sa.Column("timezone", sa.String(length=64), server_default="America/Guatemala", nullable=False),
    )

    op.create_table(
        "doctor_availability_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_availability_times"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_availability_doctor_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_doctor_availability_blocks_id"), "doctor_availability_blocks", ["id"])
    op.create_index(
        op.f("ix_doctor_availability_blocks_doctor_id"), "doctor_availability_blocks", ["doctor_id"]
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM doctor_availability_blocks")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} bloques de horario registrados. Revertir esta migración los borraría; "
            "respáldalos y elimínalos a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_doctor_availability_blocks_doctor_id"), table_name="doctor_availability_blocks")
    op.drop_index(op.f("ix_doctor_availability_blocks_id"), table_name="doctor_availability_blocks")
    op.drop_table("doctor_availability_blocks")
    op.drop_column("clinics", "timezone")
