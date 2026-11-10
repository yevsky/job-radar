import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.helpers import ADMIN_EMAIL, USER_EMAIL, auth_header


def test_list_users_without_token_returns_401(api: TestClient) -> None:
    response = api.get('/admin/users')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_users_as_user_returns_403(api: TestClient, access_token: str) -> None:
    response = api.get('/admin/users', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.usefixtures('registered_user_id')
def test_list_users_as_admin_returns_200_and_all_users(api: TestClient, admin_token: str) -> None:
    response = api.get('/admin/users', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [user['email'] for user in body] == [USER_EMAIL, ADMIN_EMAIL]
    assert all('hashed_password' not in user for user in body)
