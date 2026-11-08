"""periodontal default source

Origen 'default' para valores propuestos (llenado con valores de salud o copia
del examen anterior) que el profesional aún no editó (ODON-262). Solo amplía
los CHECK de source y agrega que un sitio vacío o una pieza sin movilidad no
pueden ser predeterminados. El downgrade se detiene si ya hay valores
predeterminados (las copias JSONB de periodontal_exam_revisions conservan su
"source" histórico y no se modifican).

Revision ID: 41b5876fa104
Revises: dd714ba31e5c
Create Date: 2026-11-07 17:47:26.756506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41b5876fa104'
down_revision: Union[str, Sequence[str], None] = 'dd714ba31e5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = (("periodontal_sites", "ck_periodontal_sites_source"), ("periodontal_teeth", "ck_periodontal_teeth_source"))


def upgrade() -> None:
    """Upgrade schema."""
    for table, name in TABLES:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, "source IN ('manual', 'default')")
    op.create_check_constraint(
        "ck_periodontal_sites_default_values", "periodontal_sites",
        "source = 'manual' OR probing_depth IS NOT NULL OR gingival_margin IS NOT NULL OR bleeding OR suppuration OR plaque",
    )
    op.create_check_constraint(
        "ck_periodontal_teeth_default_mobility", "periodontal_teeth", "source = 'manual' OR mobility IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    for table, _ in TABLES:
        count = bind.execute(sa.text(f"SELECT count(*) FROM {table} WHERE source = 'default'")).scalar()
        if count:
            raise RuntimeError(
                f"Hay {count} valores predeterminados en {table}. Revertir esta migración los dejaría "
                "inválidos; márcalos como manuales o elimínalos a mano si de verdad hay que revertirla."
            )
    op.drop_constraint("ck_periodontal_teeth_default_mobility", "periodontal_teeth", type_="check")
    op.drop_constraint("ck_periodontal_sites_default_values", "periodontal_sites", type_="check")
    for table, name in TABLES:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, "source IN ('manual')")
