from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.auth.token import create_access_token
from tests.helpers import PASSWORD, auth_header
from tests.helpers import USER_EMAIL as EMAIL

# /register tests


def test_register_returns_201_and_user_without_password(api: TestClient) -> None:
    response = api.post('/auth/register', json={'email': EMAIL, 'password': PASSWORD})

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['email'] == EMAIL
    assert 'password' not in body
    assert 'hashed_password' not in body


@pytest.mark.usefixtures('registered_user_id')
@pytest.mark.parametrize('email', [EMAIL, 'USER@Example.com'])
def test_register_with_taken_email_returns_409(api: TestClient, email: str) -> None:
    response = api.post('/auth/register', json={'email': email, 'password': PASSWORD})

    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize(
    'payload',
    [
        {'email': 'not-an-email', 'password': PASSWORD},
        {'email': EMAIL, 'password': 'short'},
        {'email': EMAIL},
    ],
)
def test_register_with_invalid_input_returns_422(api: TestClient, payload: dict[str, str]) -> None:
    response = api.post('/auth/register', json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# /login tests


@pytest.mark.usefixtures('registered_user_id')
def test_login_returns_bearer_token(api: TestClient) -> None:
    response = api.post('/auth/login', data={'username': EMAIL, 'password': PASSWORD})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['access_token']
    assert body['token_type'] == 'bearer'


@pytest.mark.usefixtures('registered_user_id')
def test_login_with_wrong_password_and_unknown_email_fail_the_same_way(api: TestClient) -> None:
    wrong_password = api.post('/auth/login', data={'username': EMAIL, 'password': 'wrong-pass'})
    unknown_email = api.post(
        '/auth/login', data={'username': 'nobody@example.com', 'password': PASSWORD}
    )

    assert wrong_password.status_code == status.HTTP_401_UNAUTHORIZED
    assert unknown_email.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_password.json() == unknown_email.json()


# /me tests


def test_me_returns_the_logged_in_user(api: TestClient, access_token: str) -> None:
    response = api.get('/auth/me', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['email'] == EMAIL


def test_me_without_token_returns_401(api: TestClient) -> None:
    response = api.get('/auth/me')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_with_garbage_token_returns_401(api: TestClient) -> None:
    response = api.get('/auth/me', headers=auth_header('not-a-real-token'))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_with_expired_token_returns_401(api: TestClient, registered_user_id: int) -> None:
    token = create_access_token(str(registered_user_id), expires_delta=timedelta(minutes=-1))

    response = api.get('/auth/me', headers=auth_header(token))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_with_token_for_missing_user_returns_401(api: TestClient) -> None:
    token = create_access_token('999999')

    response = api.get('/auth/me', headers=auth_header(token))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
