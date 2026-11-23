"""add search source switches

Revision ID: 7c2e4b9d1a35
Revises: e0a0df23f477
Create Date: 2026-11-23 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c2e4b9d1a35'
down_revision: str | Sequence[str] | None = 'e0a0df23f477'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'search_source_switches',
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('name'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('search_source_switches')
