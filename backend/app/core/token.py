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
