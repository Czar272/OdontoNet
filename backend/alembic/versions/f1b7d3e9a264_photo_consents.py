"""photo consents

Revision ID: f1b7d3e9a264
Revises: e9a4c2d7f815
Create Date: 2026-11-03 11:00:00

Consentimiento para fotografías clínicas (ODON-170):
- patient_photo_consents: una fila por versión con autorización clínica,
  uso en investigación (solo si hay autorización), fecha del documento,
  notas, autor y fecha de registro. Nunca se modifica ni se borra.
- patient_images.consent_id (obligatorio): versión del consentimiento
  vigente al subir, del mismo paciente y clínica.

No borra datos. Se detiene si ya hay imágenes registradas, porque no
tendrían un consentimiento al que vincularse. El downgrade se detiene si
hay consentimientos registrados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1b7d3e9a264"
down_revision: Union[str, Sequence[str], None] = "e9a4c2d7f815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    images = op.get_bind().execute(sa.text("SELECT count(*) FROM patient_images")).scalar()
    if images:
        raise RuntimeError(
            f"Hay {images} imágenes registradas sin consentimiento. Registra el consentimiento "
            "de esos pacientes y vincúlalo a mano antes de aplicar esta migración."
        )

    op.create_table(
        "patient_photo_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("research_use", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("signed_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("recorded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_photo_consents_version"),
        sa.CheckConstraint("granted OR NOT research_use", name="ck_photo_consents_research_requires_grant"),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["patient_id", "clinic_id"], ["patients.id", "patients.clinic_id"],
            name="fk_photo_consents_patient_clinic",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id", "clinic_id"], ["users.id", "users.clinic_id"],
            name="fk_photo_consents_author_clinic",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "version", name="uq_photo_consents_patient_version"),
        sa.UniqueConstraint("id", "patient_id", "clinic_id", name="uq_photo_consents_id_patient_clinic"),
    )
    op.create_index(op.f("ix_patient_photo_consents_id"), "patient_photo_consents", ["id"])
    op.create_index(op.f("ix_patient_photo_consents_patient_id"), "patient_photo_consents", ["patient_id"])

    op.add_column("patient_images", sa.Column("consent_id", sa.Integer(), nullable=False))
    op.create_foreign_key(
        op.f("patient_images_consent_id_fkey"), "patient_images", "patient_photo_consents", ["consent_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_patient_images_consent",
        "patient_images",
        "patient_photo_consents",
        ["consent_id", "patient_id", "clinic_id"],
        ["id", "patient_id", "clinic_id"],
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM patient_photo_consents")).scalar()
    if count:
        raise RuntimeError(
            f"Hay {count} consentimientos registrados. Revertir esta migración los borraría; "
            "respáldalos y elimínalos a mano si de verdad hay que revertirla."
        )

    op.drop_constraint("fk_patient_images_consent", "patient_images", type_="foreignkey")
    op.drop_constraint(op.f("patient_images_consent_id_fkey"), "patient_images", type_="foreignkey")
    op.drop_column("patient_images", "consent_id")
    op.drop_index(op.f("ix_patient_photo_consents_patient_id"), table_name="patient_photo_consents")
    op.drop_index(op.f("ix_patient_photo_consents_id"), table_name="patient_photo_consents")
    op.drop_table("patient_photo_consents")
