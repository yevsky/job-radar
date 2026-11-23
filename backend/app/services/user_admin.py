"""Admin actions on user accounts: list them, change a role, delete an account."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Role, User
from app.models.role import RoleName
from app.services.search import UserNotFoundError

__all__ = ['OwnAccountError', 'UserNotFoundError', 'change_role', 'delete_user', 'list_users']


class OwnAccountError(Exception):
    """An admin tried to change their own role or delete their own account.

    Blocking it means the app can never end up with no admin by accident.
    """


def list_users(db: Session) -> Sequence[User]:
    return db.scalars(select(User).options(selectinload(User.role)).order_by(User.id)).all()


def _other_user(db: Session, user_id: int, admin: User) -> User:
    """The user an admin acts on; never the admin themself."""
    if user_id == admin.id:
        raise OwnAccountError
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user


def change_role(db: Session, user_id: int, role_name: RoleName, admin: User) -> User:
    """Make a user an admin, or a normal user again."""
    user = _other_user(db, user_id, admin)
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise RuntimeError(f"Role '{role_name}' not found. Did you run the migrations?")
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int, admin: User) -> None:
    """Delete an account and everything that is only theirs.

    The database deletes the rest through ON DELETE CASCADE: profile, private offers,
    applications, CVs, analyses, chats, search runs. Public offers stay.
    """
    user = _other_user(db, user_id, admin)
    db.delete(user)
    db.commit()
