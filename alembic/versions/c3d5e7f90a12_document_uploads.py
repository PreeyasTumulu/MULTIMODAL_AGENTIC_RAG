"""document uploads

Revision ID: c3d5e7f90a12
Revises: a9c4e1d27b30
Create Date: 2026-09-17 21:00:00.000000

Private uploads have no company or fiscal year, so both become nullable, and a
document records where it came from and how far its processing has got. Every
existing row is part of the measured corpus and already indexed: the server
defaults ("corpus", "ready") describe exactly that.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d5e7f90a12'
down_revision: str | None = 'a9c4e1d27b30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('documents', 'ticker', existing_type=sa.String(length=20), nullable=True)
    op.alter_column('documents', 'fiscal_year', existing_type=sa.Integer(), nullable=True)
    op.add_column('documents', sa.Column('source', sa.String(length=20), server_default='corpus', nullable=False))
    op.add_column('documents', sa.Column('status', sa.String(length=20), server_default='ready', nullable=False))
    op.add_column('documents', sa.Column('progress', sa.Float(), server_default='0', nullable=False))
    op.add_column('documents', sa.Column('n_chunks', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('error', sa.Text(), nullable=True))
    op.create_index(op.f('ix_documents_source'), 'documents', ['source'], unique=False)


def downgrade() -> None:
    # Uploads cannot satisfy NOT NULL ticker/fiscal_year, so they go first.
    op.execute("DELETE FROM documents WHERE source = 'upload'")
    op.drop_index(op.f('ix_documents_source'), table_name='documents')
    for column in ('error', 'n_chunks', 'progress', 'status', 'source'):
        op.drop_column('documents', column)
    op.alter_column('documents', 'fiscal_year', existing_type=sa.Integer(), nullable=False)
    op.alter_column('documents', 'ticker', existing_type=sa.String(length=20), nullable=False)
