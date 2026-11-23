from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.hashing import hash_password, verify_password
from app.core.token import hash_refresh_token, new_refresh_token
from app.models import RefreshToken, Role, User
from app.models.role import RoleName
from app.schemas.user import UserRegister

DEFAULT_ROLE = RoleName.USER


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    """The refresh token is unknown, expired, revoked, or its user is gone."""


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


def issue_refresh_token(db: Session, user: User, now: datetime | None = None) -> str:
    """Start a long login for this user on one browser; return the token for the cookie."""
    now = now or datetime.now(UTC)
    token = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            created_at=now,
        )
    )
    db.commit()
    return token


def revoke_all_refresh_tokens(db: Session, user_id: int, now: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()


def _find_refresh_token(db: Session, token: str) -> RefreshToken | None:
    return db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )


def rotate_refresh_token(db: Session, token: str, now: datetime | None = None) -> tuple[User, str]:
    """Swap a valid refresh token for a new one; return its user and the new token.

    A token works once. If an already used token comes back, someone may have copied it,
    so every login of that user is revoked and they must log in again (reuse detection).
    """
    now = now or datetime.now(UTC)
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if row is None:
        raise InvalidRefreshTokenError
    if row.revoked_at is not None:
        revoke_all_refresh_tokens(db, row.user_id, now)
        raise InvalidRefreshTokenError
    if row.expires_at <= now:
        raise InvalidRefreshTokenError

    user = db.get(User, row.user_id)
    if user is None:  # the CASCADE removes tokens with the user, but be safe
        raise InvalidRefreshTokenError
    row.revoked_at = now
    db.commit()
    return user, issue_refresh_token(db, user, now)


def revoke_refresh_token(db: Session, token: str, now: datetime | None = None) -> None:
    """Log out on this browser. An unknown or already revoked token is fine."""
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = now or datetime.now(UTC)
        db.commit()
