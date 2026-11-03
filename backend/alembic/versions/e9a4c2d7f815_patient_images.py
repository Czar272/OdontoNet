"""patient images

Revision ID: e9a4c2d7f815
Revises: d2f6b8c1e937
Create Date: 2026-11-03 10:00:00

Almacenamiento privado de imágenes clínicas (ODON-166):
- patient_images: registro de cada fotografía con clínica, paciente, consulta
  y pieza dental FDI opcionales, clave del archivo en el almacenamiento
  privado, tipo, tamaño, dimensiones, huella SHA-256, autor y fecha.
- FKs compuestas para que paciente, consulta y autor sean de la clínica.

Solo crea una tabla nueva: no modifica ni borra datos. El downgrade se detiene
si ya hay imágenes registradas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9a4c2d7f815"
down_revision: Union[str, Sequence[str], None] = "d2f6b8c1e937"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPES = "'image/jpeg', 'image/png', 'image/webp'"
TOOTH_CHECK = (
    "tooth IS NULL OR "
    "(tooth / 10 BETWEEN 1 AND 4 AND tooth % 10 BETWEEN 1 AND 8) OR "
    "(tooth / 10 BETWEEN 5 AND 8 AND tooth % 10 BETWEEN 1 AND 5)"
)


def upgrade() -> None:
    op.create_table(
        "patient_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("clinical_visit_id", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"content_type IN ({TYPES})", name="ck_patient_images_content_type"),
        sa.CheckConstraint("size_bytes > 0", name="ck_patient_images_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_patient_images_dimensions"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_patient_images_sha256"),
        sa.CheckConstraint(TOOTH_CHECK, name="ck_patient_images_tooth"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["clinical_visit_id"], ["clinical_visits.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["patient_id", "clinic_id"], ["patients.id", "patients.clinic_id"],
            name="fk_patient_images_patient_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["clinical_visit_id", "clinic_id"], ["clinical_visits.id", "clinical_visits.clinic_id"],
            name="fk_patient_images_visit_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_patient_images_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "clinic_id", name="uq_patient_images_id_clinic"),
        sa.UniqueConstraint("storage_key", name="uq_patient_images_storage_key"),
    )
    op.create_index(op.f("ix_patient_images_id"), "patient_images", ["id"])
    op.create_index(op.f("ix_patient_images_patient_id"), "patient_images", ["patient_id"])


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM patient_images")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} imágenes registradas. Revertir esta migración perdería su registro; "
            "respáldalas y elimínalas a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_patient_images_patient_id"), table_name="patient_images")
    op.drop_index(op.f("ix_patient_images_id"), table_name="patient_images")
    op.drop_table("patient_images")
