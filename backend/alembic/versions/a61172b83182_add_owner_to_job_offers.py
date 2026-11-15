"""add owner to job offers

Revision ID: a61172b83182
Revises: d1082f27b120
Create Date: 2026-11-15 21:18:00.484592

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a61172b83182'
down_revision: str | Sequence[str] | None = 'd1082f27b120'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('job_offers', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_job_offers_owner_id'), 'job_offers', ['owner_id'], unique=False)
    op.create_foreign_key(
        'fk_job_offers_owner_id_users',
        'job_offers',
        'users',
        ['owner_id'],
        ['id'],
        ondelete='CASCADE',
    )
    # The old constraint allowed one row per URL. Now it's one public row per URL
    # (owner_id NULL) plus one private copy per user.
    op.drop_constraint('job_offers_url_key', 'job_offers', type_='unique')
    op.create_unique_constraint(
        'uq_job_offers_owner_id_url',
        'job_offers',
        ['owner_id', 'url'],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Private copies would break the old one-row-per-URL rule, so remove them first.
    op.execute('DELETE FROM job_offers WHERE owner_id IS NOT NULL')
    op.drop_constraint('uq_job_offers_owner_id_url', 'job_offers', type_='unique')
    op.create_unique_constraint('job_offers_url_key', 'job_offers', ['url'])
    op.drop_constraint('fk_job_offers_owner_id_users', 'job_offers', type_='foreignkey')
    op.drop_index(op.f('ix_job_offers_owner_id'), table_name='job_offers')
    op.drop_column('job_offers', 'owner_id')
