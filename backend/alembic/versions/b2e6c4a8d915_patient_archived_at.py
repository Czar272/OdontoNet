"""patient archived_at

Revision ID: b2e6c4a8d915
Revises: 9d4f1a7b2c83
Create Date: 2026-11-02 10:00:00

Estado de archivo de pacientes (ODON-123):
- patients.archived_at: NULL = activo; con fecha = archivado en ese momento.

Archivar no borra nada. La columna es nullable y sin valor por defecto, así
que todos los pacientes existentes quedan activos. El downgrade quita la
columna y con ella solo la marca de archivo, nunca pacientes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2e6c4a8d915"
down_revision: Union[str, Sequence[str], None] = "9d4f1a7b2c83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    archived = op.get_bind().execute(
        sa.text("SELECT count(*) FROM patients WHERE archived_at IS NOT NULL")
    ).scalar()
    if archived:
        raise RuntimeError(
            f"Hay {archived} pacientes archivados. Reactívalos antes de revertir "
            "esta migración para no perder su estado."
        )
    op.drop_column("patients", "archived_at")
