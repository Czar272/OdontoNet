"""appointments

Revision ID: c4f8a1d2e6b3
Revises: b2e6c4a8d915
Create Date: 2026-11-02 11:00:00

Citas de la agenda (ODON-130 / ODON-132):
- extensión btree_gist (de confianza: la puede crear el dueño de la base) para
  combinar doctor_id (=) y rangos de tiempo (&&) en una misma restricción;
- función appointment_end(inicio, minutos): fin de la cita. Se declara
  IMMUTABLE porque sumar minutos no depende de la zona horaria (a diferencia
  de sumar días o meses), y así puede usarse en la restricción de exclusión;
- uq_patients_id_clinic: permite la FK compuesta (patient_id, clinic_id);
- tabla appointments con FKs compuestas a pacientes y doctores de la misma
  clínica, duración entre 5 y 480 minutos, cinco estados y la exclusión
  ex_appointments_doctor_overlap: un doctor no tiene dos citas activas
  (programada, confirmada o atendida) que se crucen.

Es una tabla nueva: no modifica ni borra datos existentes. El downgrade se
detiene si ya hay citas registradas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c4f8a1d2e6b3"
down_revision: Union[str, Sequence[str], None] = "b2e6c4a8d915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        CREATE FUNCTION appointment_end(starts_at timestamptz, duration_minutes integer)
        RETURNS timestamptz
        LANGUAGE sql IMMUTABLE PARALLEL SAFE
        AS $$ SELECT starts_at + make_interval(mins => duration_minutes) $$
        """
    )

    op.create_unique_constraint("uq_patients_id_clinic", "patients", ["id", "clinic_id"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="scheduled", nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("duration_minutes BETWEEN 5 AND 480", name="ck_appointments_duration"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')",
            name="ck_appointments_status",
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["patient_id", "clinic_id"],
            ["patients.id", "patients.clinic_id"],
            name="fk_appointments_patient_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id", "clinic_id"],
            ["doctors.id", "doctors.clinic_id"],
            name="fk_appointments_doctor_clinic",
        ),
        postgresql.ExcludeConstraint(
            ("doctor_id", "="),
            (
                sa.text("tstzrange(starts_at, appointment_end(starts_at, duration_minutes), '[)')"),
                "&&",
            ),
            name="ex_appointments_doctor_overlap",
            using="gist",
            where=sa.text("status IN ('scheduled', 'confirmed', 'completed')"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_appointments_id"), "appointments", ["id"])
    op.create_index(op.f("ix_appointments_clinic_id"), "appointments", ["clinic_id"])
    op.create_index(op.f("ix_appointments_patient_id"), "appointments", ["patient_id"])
    op.create_index(op.f("ix_appointments_doctor_id"), "appointments", ["doctor_id"])
    op.create_index(op.f("ix_appointments_starts_at"), "appointments", ["starts_at"])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM appointments")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} citas registradas. Revertir esta migración las borraría; "
            "respáldalas y elimínalas a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_appointments_starts_at"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_doctor_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_patient_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_clinic_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_id"), table_name="appointments")
    op.drop_table("appointments")
    op.drop_constraint("uq_patients_id_clinic", "patients", type_="unique")
    op.execute("DROP FUNCTION appointment_end(timestamptz, integer)")
    # btree_gist se deja instalada: es inocua y otra tabla podría usarla.
