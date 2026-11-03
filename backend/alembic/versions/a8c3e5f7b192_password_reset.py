"""password reset

Revision ID: a8c3e5f7b192
Revises: f3a7d1c9b264
Create Date: 2026-11-02 21:00:00

Recuperación y cambio de contraseña (ODON-54):
- users.password_changed_at: momento del último cambio o restablecimiento
  de contraseña. Los tokens de sesión emitidos antes dejan de valer. Nulo
  para los usuarios existentes: sus sesiones actuales siguen igual;
- password_reset_tokens: enlaces de recuperación de un solo uso. Solo se
  guarda el hash SHA-256 del token, nunca el token.

Solo agrega una columna nula y una tabla nueva: no modifica ni borra datos.
El downgrade se detiene si ya hay enlaces emitidos o contraseñas cambiadas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a8c3e5f7b192"
down_revision: Union[str, Sequence[str], None] = "f3a7d1c9b264"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index(op.f("ix_password_reset_tokens_id"), "password_reset_tokens", ["id"])
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tokens = bind.execute(sa.text("SELECT count(*) FROM password_reset_tokens")).scalar()
    changed = bind.execute(sa.text("SELECT count(*) FROM users WHERE password_changed_at IS NOT NULL")).scalar()
    if tokens or changed:
        raise RuntimeError(
            f"Hay {tokens} enlaces de recuperación y {changed} usuarios con contraseña cambiada. "
            "Revertir esta migración borraría ese historial; respáldalo y elimínalo a mano si de verdad hay que revertirla."
        )

    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "password_changed_at")
