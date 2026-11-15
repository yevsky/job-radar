"""add posted source and description

Revision ID: 23f20acbf531
Revises: a61172b83182
Create Date: 2026-11-15 22:57:58.701368

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '23f20acbf531'
down_revision: str | Sequence[str] | None = 'a61172b83182'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE source_kind ADD VALUE IF NOT EXISTS 'posted'")
    op.add_column('job_offers', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('job_offers', 'description')
    # Postgres can't remove a value from an enum type, so 'posted' stays.
    # It's harmless: the old code simply never uses it.
