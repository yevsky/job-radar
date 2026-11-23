"""Staying logged in: the refresh cookie, POST /auth/refresh and POST /auth/logout."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.token import hash_refresh_token
from app.models import RefreshToken, User
from app.routers.auth import REFRESH_COOKIE
from app.services.auth import InvalidRefreshTokenError, issue_refresh_token, rotate_refresh_token
from tests.helpers import PASSWORD, USER_EMAIL, auth_header


def login(api: TestClient) -> str:
    """Log in; the client keeps the refresh cookie like a browser. Return the access token."""
    response = api.post('/auth/login', data={'username': USER_EMAIL, 'password': PASSWORD})
    assert response.status_code == status.HTTP_200_OK
    return str(response.json()['access_token'])


def use_cookie(api: TestClient, token: str) -> None:
    """Put this refresh token in the client's cookie jar, as the only cookie."""
    api.cookies.clear()
    api.cookies.set(REFRESH_COOKIE, token)


def refresh(api: TestClient) -> tuple[int, str | None]:
    response = api.post('/auth/refresh')
    token = response.json().get('access_token') if response.status_code == 200 else None
    return response.status_code, token


@pytest.mark.usefixtures('registered_user_id')
def test_login_sets_an_http_only_refresh_cookie(api: TestClient) -> None:
    response = api.post('/auth/login', data={'username': USER_EMAIL, 'password': PASSWORD})

    cookie = response.headers['set-cookie']
    assert cookie.startswith(f'{REFRESH_COOKIE}=')
    assert 'HttpOnly' in cookie
    assert 'SameSite=lax' in cookie
    assert 'Max-Age=2592000' in cookie  # 30 days


@pytest.mark.usefixtures('registered_user_id')
def test_refresh_gives_a_working_access_token(api: TestClient) -> None:
    login(api)

    code, token = refresh(api)

    assert code == status.HTTP_200_OK
    assert token is not None
    me = api.get('/auth/me', headers=auth_header(token))
    assert me.json()['email'] == USER_EMAIL


@pytest.mark.usefixtures('registered_user_id')
def test_each_refresh_replaces_the_cookie(api: TestClient) -> None:
    login(api)
    first = api.cookies[REFRESH_COOKIE]

    refresh(api)

    assert api.cookies[REFRESH_COOKIE] != first
    assert refresh(api)[0] == status.HTTP_200_OK  # the new one works again


@pytest.mark.usefixtures('registered_user_id')
def test_reusing_an_old_refresh_token_ends_every_login(api: TestClient) -> None:
    """A used token coming back means it may have been copied: log the user out everywhere."""
    login(api)
    stolen = api.cookies[REFRESH_COOKIE]
    refresh(api)  # the real browser moves on to a new token
    current = api.cookies[REFRESH_COOKIE]

    use_cookie(api, stolen)
    assert refresh(api)[0] == status.HTTP_401_UNAUTHORIZED

    use_cookie(api, current)
    assert refresh(api)[0] == status.HTTP_401_UNAUTHORIZED


def test_refresh_without_a_cookie_returns_401(api: TestClient) -> None:
    response = api.post('/auth/refresh')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_with_an_unknown_token_returns_401_and_clears_the_cookie(api: TestClient) -> None:
    use_cookie(api, 'made-up')

    response = api.post('/auth/refresh')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers['set-cookie'].startswith(f'{REFRESH_COOKIE}=""')


@pytest.mark.usefixtures('registered_user_id')
def test_logout_ends_the_login(api: TestClient) -> None:
    login(api)

    response = api.post('/auth/logout')

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert REFRESH_COOKIE not in api.cookies
    assert refresh(api)[0] == status.HTTP_401_UNAUTHORIZED


@pytest.mark.usefixtures('registered_user_id')
def test_logout_on_one_browser_keeps_the_other_logged_in(
    api: TestClient, client: TestClient
) -> None:
    login(api)
    other_browser = TestClient(client.app)
    other_browser.post('/auth/login', data={'username': USER_EMAIL, 'password': PASSWORD})

    api.post('/auth/logout')

    assert other_browser.post('/auth/refresh').status_code == status.HTTP_200_OK


def test_logout_without_a_cookie_is_fine(api: TestClient) -> None:
    assert api.post('/auth/logout').status_code == status.HTTP_204_NO_CONTENT


def test_only_a_hash_of_the_token_is_stored(
    api: TestClient, db: Session, registered_user_id: int
) -> None:
    del registered_user_id
    login(api)
    token = api.cookies[REFRESH_COOKIE]

    stored = db.scalars(select(RefreshToken.token_hash)).all()

    assert stored == [hash_refresh_token(token)]
    assert token not in stored


def test_deleting_the_user_deletes_their_refresh_tokens(
    api: TestClient, admin_token: str, registered_user_id: int, db: Session
) -> None:
    login(api)

    api.delete(f'/admin/users/{registered_user_id}', headers=auth_header(admin_token))

    assert refresh(api)[0] == status.HTTP_401_UNAUTHORIZED
    owners = db.scalars(select(RefreshToken.user_id)).all()
    assert registered_user_id not in owners


# expiry, with the service and a fixed clock


def test_token_expires_after_30_days_without_use(db: Session, registered_user_id: int) -> None:
    user = db.get(User, registered_user_id)
    assert user is not None
    start = datetime(2026, 11, 1, tzinfo=UTC)
    token = issue_refresh_token(db, user, now=start)

    with pytest.raises(InvalidRefreshTokenError):
        rotate_refresh_token(db, token, now=start + timedelta(days=30, seconds=1))


def test_using_the_app_renews_the_30_days(db: Session, registered_user_id: int) -> None:
    user = db.get(User, registered_user_id)
    assert user is not None
    start = datetime(2026, 11, 1, tzinfo=UTC)
    token = issue_refresh_token(db, user, now=start)

    _, token = rotate_refresh_token(db, token, now=start + timedelta(days=20))
    _, token = rotate_refresh_token(db, token, now=start + timedelta(days=40))

    assert rotate_refresh_token(db, token, now=start + timedelta(days=60))[0].id == user.id
