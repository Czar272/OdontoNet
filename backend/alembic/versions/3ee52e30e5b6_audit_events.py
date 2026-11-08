"""audit events

Auditoría persistente de cambios y exportaciones (ODON-222). Tabla de solo
agregado: un trigger rechaza UPDATE, DELETE y TRUNCATE. Las pruebas pueden
vaciarla con SET LOCAL odontonet.allow_audit_purge = 'on', solo en bases cuyo
nombre termina en _test (en desarrollo y producción no tiene efecto). El downgrade se
detiene si ya hay eventos (no se pierde la auditoría).

Revision ID: 3ee52e30e5b6
Revises: 5f23eb13bd86
Create Date: 2026-11-08 00:17:10.769643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3ee52e30e5b6'
down_revision: Union[str, Sequence[str], None] = '5f23eb13bd86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=False),
    sa.Column('actor_role', sa.String(length=20), nullable=False),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('patient_id', sa.Integer(), nullable=True),
    sa.Column('fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('prev_hash', sa.String(length=64), nullable=True),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id', 'clinic_id'], ['users.id', 'users.clinic_id'], name='fk_audit_events_actor_clinic'),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], name='fk_audit_events_clinic'),
    sa.ForeignKeyConstraint(['patient_id', 'clinic_id'], ['patients.id', 'patients.clinic_id'], name='fk_audit_events_patient_clinic'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_events_clinic_actor', 'audit_events', ['clinic_id', 'actor_user_id', 'id'], unique=False)
    op.create_index('ix_audit_events_clinic_id', 'audit_events', ['clinic_id', 'id'], unique=False)
    op.create_index('ix_audit_events_clinic_occurred', 'audit_events', ['clinic_id', 'occurred_at'], unique=False)
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('odontonet.allow_audit_purge', true) = 'on'
               AND current_database() LIKE '%\\_test' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'audit_events es de solo agregado: no admite %', TG_OP;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER audit_events_no_update_delete BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()
    """)
    op.execute("""
        CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only()
    """)


def downgrade() -> None:
    """Downgrade schema."""
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM audit_events")).scalar()
    if count:
        raise RuntimeError(
            f"audit_events tiene {count} eventos: el downgrade borraría la auditoría. Respáldala y decide antes de bajar."
        )
    op.execute("DROP TRIGGER audit_events_no_truncate ON audit_events")
    op.execute("DROP TRIGGER audit_events_no_update_delete ON audit_events")
    op.execute("DROP FUNCTION audit_events_append_only()")
    op.drop_index('ix_audit_events_clinic_occurred', table_name='audit_events')
    op.drop_index('ix_audit_events_clinic_id', table_name='audit_events')
    op.drop_index('ix_audit_events_clinic_actor', table_name='audit_events')
    op.drop_table('audit_events')
