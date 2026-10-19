from datetime import timedelta

import jwt
import pytest

from app.auth.token import create_access_token, decode_access_token


def test_decode_returns_subject_of_created_token() -> None:
    token = create_access_token('5')

    assert decode_access_token(token) == '5'


def test_token_made_with_small_timedelta_raises_error() -> None:
    token = create_access_token('5', timedelta(minutes=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)
