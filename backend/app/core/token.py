import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        'sub': subject,
        'exp': datetime.now(UTC) + expires_delta,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token, settings.jwt_secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm]
    )
    return str(payload['sub'])


def new_refresh_token() -> str:
    """A random, unguessable token (43 characters). It is not a JWT: the database knows it."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """What the database stores instead of the token itself.

    SHA-256 is enough here (unlike for passwords) because the token is random, not chosen
    by a person, so there is nothing to guess.
    """
    return hashlib.sha256(token.encode()).hexdigest()
