"""public offers are posted

Every public offer (no owner) now has the source `posted`, whether an admin imported it from
a file or it came from the demo seed. `manual` is kept for offers a user added for themself.

Revision ID: b3e8f1c7a2d4
Revises: 9f3a6d2c8e14
Create Date: 2026-11-23 19:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3e8f1c7a2d4'
down_revision: str | Sequence[str] | None = '9f3a6d2c8e14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # On a fresh database, 'posted' is added to the enum earlier in the same run, and
    # Postgres can use a new enum value only after it is committed: commit first.
    with op.get_context().autocommit_block():
        op.execute("UPDATE job_offers SET source = 'posted' WHERE owner_id IS NULL")


def downgrade() -> None:
    """Downgrade schema.

    Nothing to undo: which public offers were 'manual' before isn't stored anywhere, and
    'posted' is a valid source for all of them.
    """
