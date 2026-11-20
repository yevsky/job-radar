"""add applications and status history

Revision ID: d01b22297888
Revises: 4f385218f768
Create Date: 2026-11-18 00:50:46.986025

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd01b22297888'
down_revision: str | Sequence[str] | None = '4f385218f768'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = (
    'saved',
    'applied',
    'screening',
    'interview',
    'offer',
    'accepted',
    'rejected',
    'declined',
)
# Created once below; both tables then reuse it (create_type=False).
application_status = postgresql.ENUM(*STATUSES, name='application_status', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    application_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_offer_id', sa.Integer(), nullable=False),
        sa.Column('status', application_status, nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('interview_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_offer_id'], ['job_offers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'job_offer_id', name='uq_applications_user_id_job_offer_id'),
    )
    op.create_index(
        op.f('ix_applications_job_offer_id'), 'applications', ['job_offer_id'], unique=False
    )
    op.create_index(op.f('ix_applications_user_id'), 'applications', ['user_id'], unique=False)

    op.create_table(
        'application_status_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('status', application_status, nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_application_status_changes_application_id'),
        'application_status_changes',
        ['application_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_application_status_changes_application_id'),
        table_name='application_status_changes',
    )
    op.drop_table('application_status_changes')
    op.drop_index(op.f('ix_applications_user_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_job_offer_id'), table_name='applications')
    op.drop_table('applications')
    application_status.drop(op.get_bind(), checkfirst=True)
