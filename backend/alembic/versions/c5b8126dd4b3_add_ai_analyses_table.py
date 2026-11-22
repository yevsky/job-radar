"""add ai_analyses table

Revision ID: c5b8126dd4b3
Revises: 46986e627c3f
Create Date: 2026-11-22 16:01:07.087540

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c5b8126dd4b3'
down_revision: str | Sequence[str] | None = '46986e627c3f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_offer_id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.SmallInteger(), nullable=False),
        sa.Column('breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('red_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('matched_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('missing_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('score BETWEEN 0 AND 100', name='ck_ai_analyses_score_0_100'),
        sa.ForeignKeyConstraint(['job_offer_id'], ['job_offers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_ai_analyses_job_offer_id'), 'ai_analyses', ['job_offer_id'], unique=False
    )
    op.create_index(
        'ix_ai_analyses_user_id_job_offer_id_created_at',
        'ai_analyses',
        ['user_id', 'job_offer_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ai_analyses_user_id_job_offer_id_created_at', table_name='ai_analyses')
    op.drop_index(op.f('ix_ai_analyses_job_offer_id'), table_name='ai_analyses')
    op.drop_table('ai_analyses')
