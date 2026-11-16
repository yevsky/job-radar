"""add search runs and user search limit

Revision ID: 47d4129f6aa1
Revises: 23f20acbf531
Create Date: 2026-11-17 00:09:17.448734

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '47d4129f6aa1'
down_revision: str | Sequence[str] | None = '23f20acbf531'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'search_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_search_runs_user_id_created_at', 'search_runs', ['user_id', 'created_at'], unique=False
    )
    op.add_column('users', sa.Column('search_daily_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'search_daily_limit')
    op.drop_index('ix_search_runs_user_id_created_at', table_name='search_runs')
    op.drop_table('search_runs')
