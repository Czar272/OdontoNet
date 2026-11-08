"""patients created_at

Fecha de alta del paciente para los indicadores de pacientes nuevos (ODON-202).
Se agrega sin valor para las filas existentes (su fecha real no se conoce) y
con valor por defecto now() para las nuevas.

Revision ID: 23ac2035a1f6
Revises: 41b5876fa104
Create Date: 2026-11-07 19:19:32.534103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23ac2035a1f6'
down_revision: Union[str, Sequence[str], None] = '41b5876fa104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Primero sin valor por defecto: así las filas existentes quedan en NULL.
    op.add_column("patients", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("patients", "created_at", server_default=sa.func.now())
    op.create_index("ix_patients_clinic_created_at", "patients", ["clinic_id", "created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    # Solo se pierde la fecha de alta, que es informativa.
    op.drop_index("ix_patients_clinic_created_at", table_name="patients")
    op.drop_column("patients", "created_at")
