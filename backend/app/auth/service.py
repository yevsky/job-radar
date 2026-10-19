from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.hashing import hash_password, verify_password
from app.auth.schemas import UserRegister
from app.models import Role, User

DEFAULT_ROLE = 'user'


class EmailAlreadyRegisteredError(Exception):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, data: UserRegister) -> User:
    """Create a new user account with the default role."""
    email = _normalize_email(data.email)

    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailAlreadyRegisteredError

    role = db.scalar(select(Role).where(Role.name == DEFAULT_ROLE))
    if role is None:
        raise RuntimeError(f"Role '{DEFAULT_ROLE}' not found. Did you run the migrations?")

    user = User(email=email, hashed_password=hash_password(data.password), role_id=role.id)

    db.add(user)
    try:
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise EmailAlreadyRegisteredError from err
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if the credentials are valid, otherwise None."""
    user = db.scalar(select(User).where(User.email == _normalize_email(email)))
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
