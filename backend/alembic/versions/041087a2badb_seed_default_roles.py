"""seed default roles

Revision ID: 041087a2badb
Revises: 82273e5be23b
Create Date: 2026-10-11 19:41:56.293645

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '041087a2badb'
down_revision: str | Sequence[str] | None = '82273e5be23b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

roles_table = sa.table('roles', sa.column('name', sa.String))


def upgrade() -> None:
    op.bulk_insert(roles_table, [{'name': 'user'}, {'name': 'admin'}])
    pass


def downgrade() -> None:
    op.execute(roles_table.delete().where(roles_table.c.name.in_(['user', 'admin'])))
    pass
