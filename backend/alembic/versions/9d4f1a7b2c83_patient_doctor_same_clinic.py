"""patient doctor same clinic

Revision ID: 9d4f1a7b2c83
Revises: 7b3e9d2c5a61
Create Date: 2026-11-01 02:45:00

Garantiza en la base que el doctor asignado a un paciente pertenece a la misma
clínica que el paciente (ODON-98):
- uq_doctors_id_clinic: clave única (id, clinic_id) en doctors;
- fk_patients_doctor_clinic: patients(doctor_id, clinic_id) → doctors(id, clinic_id).
Con doctor_id NULL la restricción no aplica (el doctor es opcional).

No elimina ni corrige datos: si encuentra pacientes con doctor de otra clínica,
se detiene con la lista para revisarlos a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "9d4f1a7b2c83"
down_revision: Union[str, Sequence[str], None] = "7b3e9d2c5a61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    mismatched = op.get_bind().execute(
        sa.text(
            "SELECT p.id, p.clinic_id, d.clinic_id FROM patients p "
            "JOIN doctors d ON d.id = p.doctor_id WHERE p.clinic_id <> d.clinic_id"
        )
    ).fetchall()
    if mismatched:
        detail = ", ".join(
            f"paciente {row[0]} en clínica {row[1]} con doctor de clínica {row[2]}"
            for row in mismatched
        )
        raise RuntimeError(
            f"Hay pacientes con un doctor de otra clínica: {detail}. "
            "Reasígnalos o quita el doctor antes de migrar."
        )

    op.create_unique_constraint("uq_doctors_id_clinic", "doctors", ["id", "clinic_id"])
    op.create_foreign_key(
        "fk_patients_doctor_clinic",
        "patients",
        "doctors",
        ["doctor_id", "clinic_id"],
        ["id", "clinic_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_patients_doctor_clinic", "patients", type_="foreignkey")
    op.drop_constraint("uq_doctors_id_clinic", "doctors", type_="unique")
