"""image metadata, revisions and access log

Revision ID: b7d9f1a3c605
Revises: a3c5e7b9d102
Create Date: 2026-11-04 09:00:00

Metadatos, versiones y auditoría de acceso de imágenes (ODON-178):
- patient_images: origin, view y taken_on (opcionales; null = «sin
  registrar» en imágenes anteriores), revision, y anulación con motivo
  (voided_at, voided_by_user_id, void_reason). El archivo no cambia.
- patient_image_revisions: copia de los metadatos en cada guardado. Las
  imágenes existentes reciben su revisión 1 con el autor y la fecha de subida.
- image_access_logs: cada apertura del original (quién, cuándo, qué imagen).

No modifica ni borra datos existentes: agrega columnas y tablas, y copia los
metadatos actuales como revisión 1. El downgrade se detiene si ya hay
correcciones, anulaciones o accesos registrados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7d9f1a3c605"
down_revision: Union[str, Sequence[str], None] = "a3c5e7b9d102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORIGINS = "'intraoral_camera', 'phone', 'camera', 'external'"
VIEWS = "'frontal', 'right_lateral', 'left_lateral', 'upper_occlusal', 'lower_occlusal', 'detail', 'other'"
TOOTH_CHECK = (
    "tooth IS NULL OR "
    "(tooth / 10 BETWEEN 1 AND 4 AND tooth % 10 BETWEEN 1 AND 8) OR "
    "(tooth / 10 BETWEEN 5 AND 8 AND tooth % 10 BETWEEN 1 AND 5)"
)


def upgrade() -> None:
    op.add_column("patient_images", sa.Column("origin", sa.String(length=20), nullable=True))
    op.add_column("patient_images", sa.Column("view", sa.String(length=20), nullable=True))
    op.add_column("patient_images", sa.Column("taken_on", sa.Date(), nullable=True))
    op.add_column("patient_images", sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
    op.add_column("patient_images", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("patient_images", sa.Column("voided_by_user_id", sa.Integer(), nullable=True))
    op.add_column("patient_images", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_check_constraint("ck_patient_images_origin", "patient_images", f"origin IS NULL OR origin IN ({ORIGINS})")
    op.create_check_constraint("ck_patient_images_view", "patient_images", f"view IS NULL OR view IN ({VIEWS})")
    op.create_check_constraint("ck_patient_images_revision", "patient_images", "revision >= 1")
    op.create_check_constraint(
        "ck_patient_images_void",
        "patient_images",
        "(voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL) OR "
        "(voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)",
    )
    op.create_foreign_key(
        op.f("patient_images_voided_by_user_id_fkey"), "patient_images", "users", ["voided_by_user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_patient_images_voided_by_clinic",
        "patient_images",
        "users",
        ["voided_by_user_id", "clinic_id"],
        ["id", "clinic_id"],
    )

    op.create_table(
        "patient_image_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=True),
        sa.Column("view", sa.String(length=20), nullable=True),
        sa.Column("taken_on", sa.Date(), nullable=True),
        sa.Column("clinical_visit_id", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("edited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_image_revisions_revision"),
        sa.CheckConstraint(f"origin IS NULL OR origin IN ({ORIGINS})", name="ck_image_revisions_origin"),
        sa.CheckConstraint(f"view IS NULL OR view IN ({VIEWS})", name="ck_image_revisions_view"),
        sa.CheckConstraint(TOOTH_CHECK, name="ck_image_revisions_tooth"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["image_id"], ["patient_images.id"]),
        sa.ForeignKeyConstraint(["clinical_visit_id"], ["clinical_visits.id"]),
        sa.ForeignKeyConstraint(["edited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["image_id", "clinic_id"], ["patient_images.id", "patient_images.clinic_id"],
            name="fk_image_revisions_image_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["edited_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_image_revisions_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id", "revision", name="uq_image_revisions_image_revision"),
    )
    op.create_index(op.f("ix_patient_image_revisions_id"), "patient_image_revisions", ["id"])
    op.create_index(op.f("ix_patient_image_revisions_image_id"), "patient_image_revisions", ["image_id"])

    # Revisión 1 de las imágenes existentes, con su autor y fecha de subida.
    op.execute(
        "INSERT INTO patient_image_revisions "
        "(clinic_id, image_id, revision, clinical_visit_id, tooth, edited_by_user_id, edited_at) "
        "SELECT clinic_id, id, 1, clinical_visit_id, tooth, uploaded_by_user_id, uploaded_at FROM patient_images"
    )

    op.create_table(
        "image_access_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["image_id"], ["patient_images.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["image_id", "clinic_id"], ["patient_images.id", "patient_images.clinic_id"],
            name="fk_image_access_image_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "clinic_id"], ["users.id", "users.clinic_id"], name="fk_image_access_user_clinic"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_image_access_logs_id"), "image_access_logs", ["id"])
    op.create_index(op.f("ix_image_access_logs_image_id"), "image_access_logs", ["image_id"])


def downgrade() -> None:
    bind = op.get_bind()
    pending = {
        "accesos registrados": "SELECT count(*) FROM image_access_logs",
        "correcciones de metadatos": "SELECT count(*) FROM patient_image_revisions WHERE revision > 1",
        "imágenes anuladas": "SELECT count(*) FROM patient_images WHERE voided_at IS NOT NULL",
        "imágenes con origen, vista o fecha de toma": (
            "SELECT count(*) FROM patient_images WHERE origin IS NOT NULL OR view IS NOT NULL OR taken_on IS NOT NULL"
        ),
    }
    found = {name: bind.execute(sa.text(sql)).scalar() for name, sql in pending.items()}
    found = {name: count for name, count in found.items() if count}
    if found:
        detail = ", ".join(f"{count} {name}" for name, count in found.items())
        raise RuntimeError(
            f"Hay {detail}. Revertir esta migración los perdería; respáldalos y elimínalos a mano "
            "si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_image_access_logs_image_id"), table_name="image_access_logs")
    op.drop_index(op.f("ix_image_access_logs_id"), table_name="image_access_logs")
    op.drop_table("image_access_logs")
    op.drop_index(op.f("ix_patient_image_revisions_image_id"), table_name="patient_image_revisions")
    op.drop_index(op.f("ix_patient_image_revisions_id"), table_name="patient_image_revisions")
    op.drop_table("patient_image_revisions")
    op.drop_constraint("fk_patient_images_voided_by_clinic", "patient_images", type_="foreignkey")
    op.drop_constraint(op.f("patient_images_voided_by_user_id_fkey"), "patient_images", type_="foreignkey")
    for name in ("ck_patient_images_void", "ck_patient_images_revision", "ck_patient_images_view", "ck_patient_images_origin"):
        op.drop_constraint(name, "patient_images", type_="check")
    for column in ("void_reason", "voided_by_user_id", "voided_at", "revision", "taken_on", "view", "origin"):
        op.drop_column("patient_images", column)
