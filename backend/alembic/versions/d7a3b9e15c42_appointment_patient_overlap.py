"""appointment patient overlap

Revision ID: d7a3b9e15c42
Revises: c4f8a1d2e6b3
Create Date: 2026-11-02 11:30:00

Un paciente no tiene dos citas activas que se crucen, aunque sean con doctores
distintos (decisión del 2026-11-02, ODON-134):
- ex_appointments_patient_overlap: igual que la del doctor, por patient_id.

No borra ni corrige datos: si ya hay citas que se cruzan para un mismo
paciente, se detiene con la lista para resolverlas a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7a3b9e15c42"
down_revision: Union[str, Sequence[str], None] = "c4f8a1d2e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BLOCKING = "('scheduled', 'confirmed', 'completed')"


def upgrade() -> None:
    overlapping = op.get_bind().execute(
        sa.text(
            "SELECT a.patient_id, a.id, b.id FROM appointments a "
            "JOIN appointments b ON a.patient_id = b.patient_id AND a.id < b.id "
            f"WHERE a.status IN {_BLOCKING} AND b.status IN {_BLOCKING} "
            "AND tstzrange(a.starts_at, appointment_end(a.starts_at, a.duration_minutes), '[)') "
            "&& tstzrange(b.starts_at, appointment_end(b.starts_at, b.duration_minutes), '[)')"
        )
    ).fetchall()
    if overlapping:
        detail = ", ".join(f"paciente {row[0]}: citas {row[1]} y {row[2]}" for row in overlapping)
        raise RuntimeError(
            f"Hay citas que se cruzan para un mismo paciente: {detail}. "
            "Reprograma o cancela una de cada par antes de migrar."
        )

    # SQL directo: create_exclude_constraint no acepta expresiones de texto.
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT ex_appointments_patient_overlap "
        "EXCLUDE USING gist (patient_id WITH =, "
        "tstzrange(starts_at, appointment_end(starts_at, duration_minutes), '[)') WITH &&) "
        f"WHERE (status IN {_BLOCKING})"
    )


def downgrade() -> None:
    op.drop_constraint("ex_appointments_patient_overlap", "appointments")
