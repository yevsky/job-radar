"""SQLAlchemy models: the shape of the database tables."""

from app.models.role import Role
from app.models.user import User

__all__ = [
    'Role',
    'User',
]
