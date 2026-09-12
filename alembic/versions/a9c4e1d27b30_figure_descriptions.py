"""figure descriptions

Revision ID: a9c4e1d27b30
Revises: e72036aab5e4
Create Date: 2026-09-12 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
revision: str = 'a9c4e1d27b30'
down_revision: str | None = 'e72036aab5e4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('figure_descriptions',
    sa.Column('element_id', sa.String(length=120), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['element_id'], ['elements.element_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('element_id')
    )
    op.create_index(op.f('ix_figure_descriptions_kind'), 'figure_descriptions', ['kind'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_figure_descriptions_kind'), table_name='figure_descriptions')
    op.drop_table('figure_descriptions')
