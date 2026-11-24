"""drop name and bio from profiles

Revision ID: 8b4f2d6a1c37
Revises: 5d7a1e3c9b42
Create Date: 2026-11-24 19:00:00.000000

The app never used them (the AI and search get only job fields), so they are not kept:
data minimisation. The CV's career snapshot (resumes.insights) describes the person instead.
Downgrade brings the columns back empty: the dropped values can't be restored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8b4f2d6a1c37'
down_revision: str | Sequence[str] | None = '5d7a1e3c9b42'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('user_profiles', 'bio')
    op.drop_column('user_profiles', 'last_name')
    op.drop_column('user_profiles', 'first_name')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('user_profiles', sa.Column('first_name', sa.String(length=120), nullable=True))
    op.add_column('user_profiles', sa.Column('last_name', sa.String(length=120), nullable=True))
    op.add_column('user_profiles', sa.Column('bio', sa.Text(), nullable=True))
