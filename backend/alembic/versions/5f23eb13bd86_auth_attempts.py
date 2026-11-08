"""auth attempts

Intentos de autenticación para el límite de tasa de login y recuperación
(ODON-230). Solo datos operativos (hash del correo, IP, fecha), sin datos
clínicos; el downgrade solo pierde intentos recientes, que se depuran a diario.

Revision ID: 5f23eb13bd86
Revises: 23ac2035a1f6
Create Date: 2026-11-07 22:33:15.726652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f23eb13bd86'
down_revision: Union[str, Sequence[str], None] = '23ac2035a1f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('auth_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('account_key', sa.String(length=64), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('login', 'password_reset', 'password_reset_confirm')", name='ck_auth_attempts_kind'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_auth_attempts_account', 'auth_attempts', ['kind', 'account_key', 'attempted_at'], unique=False)
    op.create_index('ix_auth_attempts_ip', 'auth_attempts', ['kind', 'ip', 'attempted_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_auth_attempts_ip', table_name='auth_attempts')
    op.drop_index('ix_auth_attempts_account', table_name='auth_attempts')
    op.drop_table('auth_attempts')
