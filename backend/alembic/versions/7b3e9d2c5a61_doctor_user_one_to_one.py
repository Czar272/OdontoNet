"""doctor-user one to one and same clinic

Revision ID: 7b3e9d2c5a61
Revises: 4c1d2e8f9a10
Create Date: 2026-11-01 00:10:00

Refuerza en la base la relación entre User y Doctor (ODON-78):
- un usuario tiene como máximo un perfil de doctor (uq_doctors_user_id);
- el perfil pertenece a la misma clínica que su usuario (fk_doctors_user_clinic,
  que necesita la clave única uq_users_id_clinic).

No elimina ni corrige datos: si encuentra perfiles duplicados o de otra clínica,
se detiene con la lista para revisarlos a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "7b3e9d2c5a61"
down_revision: Union[str, Sequence[str], None] = "4c1d2e8f9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_existing_data() -> None:
    bind = op.get_bind()

    duplicated = bind.execute(
        sa.text(
            "SELECT user_id, count(*) FROM doctors GROUP BY user_id HAVING count(*) > 1"
        )
    ).fetchall()
    if duplicated:
        detail = ", ".join(f"user_id={row[0]} ({row[1]} perfiles)" for row in duplicated)
        raise RuntimeError(
            "Hay usuarios con más de un perfil de doctor: "
            f"{detail}. Revísalos y deja uno por usuario antes de migrar."
        )

    mismatched = bind.execute(
        sa.text(
            "SELECT d.id, d.clinic_id, u.clinic_id FROM doctors d "
            "JOIN users u ON u.id = d.user_id WHERE d.clinic_id <> u.clinic_id"
        )
    ).fetchall()
    if mismatched:
        detail = ", ".join(
            f"doctor {row[0]} en clínica {row[1]} con usuario de clínica {row[2]}"
            for row in mismatched
        )
        raise RuntimeError(
            f"Hay perfiles de doctor en otra clínica que su usuario: {detail}. "
            "Corrígelos antes de migrar."
        )


def upgrade() -> None:
    _check_existing_data()
    op.create_unique_constraint("uq_doctors_user_id", "doctors", ["user_id"])
    op.create_unique_constraint("uq_users_id_clinic", "users", ["id", "clinic_id"])
    op.create_foreign_key(
        "fk_doctors_user_clinic",
        "doctors",
        "users",
        ["user_id", "clinic_id"],
        ["id", "clinic_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_doctors_user_clinic", "doctors", type_="foreignkey")
    op.drop_constraint("uq_users_id_clinic", "users", type_="unique")
    op.drop_constraint("uq_doctors_user_id", "doctors", type_="unique")
