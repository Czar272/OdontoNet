"""patient email unique per clinic and clinic_id indexes

Revision ID: 4c1d2e8f9a10
Revises: e7aac1fc989e
Create Date: 2026-10-31 17:30:00

Cambia la unicidad del correo del paciente de global a por clínica, para que
una clínica no pueda descubrir correos registrados en otra (ODON-62).
Los correos vacíos ('') se normalizan a NULL antes de crear la restricción.
No elimina filas ni columnas.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "4c1d2e8f9a10"
down_revision: Union[str, Sequence[str], None] = "e7aac1fc989e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE patients SET email = NULL WHERE trim(email) = ''")
    op.drop_constraint("patients_email_key", "patients", type_="unique")
    op.create_unique_constraint(
        "uq_patients_clinic_email", "patients", ["clinic_id", "email"]
    )
    op.create_index(op.f("ix_patients_clinic_id"), "patients", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_doctors_clinic_id"), "doctors", ["clinic_id"], unique=False)


def downgrade() -> None:
    # Falla si dos clínicas comparten un correo de paciente: revisar antes de revertir.
    op.drop_index(op.f("ix_doctors_clinic_id"), table_name="doctors")
    op.drop_index(op.f("ix_patients_clinic_id"), table_name="patients")
    op.drop_constraint("uq_patients_clinic_email", "patients", type_="unique")
    op.create_unique_constraint("patients_email_key", "patients", ["email"])
