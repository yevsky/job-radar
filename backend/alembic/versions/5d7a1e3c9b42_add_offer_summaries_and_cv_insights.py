"""add offer summaries and cv insights

Revision ID: 5d7a1e3c9b42
Revises: b3e8f1c7a2d4
Create Date: 2026-11-24 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5d7a1e3c9b42'
down_revision: str | Sequence[str] | None = 'b3e8f1c7a2d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'job_offers', sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column('job_offers', sa.Column('summary_with', sa.String(length=100), nullable=True))
    op.add_column(
        'job_offers', sa.Column('summary_prompt_version', sa.String(length=50), nullable=True)
    )
    op.add_column(
        'job_offers', sa.Column('summarized_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'resumes', sa.Column('insights', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column('resumes', sa.Column('insights_with', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('resumes', 'insights_with')
    op.drop_column('resumes', 'insights')
    op.drop_column('job_offers', 'summarized_at')
    op.drop_column('job_offers', 'summary_prompt_version')
    op.drop_column('job_offers', 'summary_with')
    op.drop_column('job_offers', 'summary')
