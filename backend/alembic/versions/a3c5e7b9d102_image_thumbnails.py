"""image thumbnails

Revision ID: a3c5e7b9d102
Revises: f1b7d3e9a264
Create Date: 2026-11-03 19:00:00

Galería de imágenes clínicas (ODON-174):
- patient_images.thumbnail_key (opcional, único): miniatura en el
  almacenamiento privado. Las imágenes subidas antes de esta migración
  generan la suya la primera vez que se pide.

Solo agrega una columna: no modifica ni borra datos.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3c5e7b9d102"
down_revision: Union[str, Sequence[str], None] = "f1b7d3e9a264"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patient_images", sa.Column("thumbnail_key", sa.String(length=80), nullable=True))
    op.create_unique_constraint("uq_patient_images_thumbnail_key", "patient_images", ["thumbnail_key"])


def downgrade() -> None:
    # Las miniaturas se regeneran desde el original: quitar la columna no
    # pierde información clínica (los archivos quedan como huérfanos que
    # verify_images reporta).
    op.drop_constraint("uq_patient_images_thumbnail_key", "patient_images", type_="unique")
    op.drop_column("patient_images", "thumbnail_key")
