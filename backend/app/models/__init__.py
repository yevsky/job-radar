"""SQLAlchemy models: the shape of the database tables."""

from app.models.role import Role
from app.models.user import User
from app.models.user_profile import UserProfile

__all__ = ['Role', 'User', 'UserProfile']
