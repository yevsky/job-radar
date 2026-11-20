from fastapi import status
from fastapi.testclient import TestClient

from tests.helpers import USER_EMAIL, auth_header


def test_user_list_shows_each_users_search_limit(
    api: TestClient, admin_token: str, registered_user_id: int
) -> None:
    api.put(
        f'/admin/users/{registered_user_id}/search-limit',
        json={'search_daily_limit': 25},
        headers=auth_header(admin_token),
    )

    response = api.get('/admin/users', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_200_OK
    limits = {user['email']: user['search_daily_limit'] for user in response.json()}
    assert limits[USER_EMAIL] == 25


def test_user_list_shows_none_for_the_default_limit(
    api: TestClient, admin_token: str, registered_user_id: int
) -> None:
    del registered_user_id

    users = api.get('/admin/users', headers=auth_header(admin_token)).json()

    assert all(user['search_daily_limit'] is None for user in users)


def test_auth_me_does_not_show_the_limit(api: TestClient, access_token: str) -> None:
    body = api.get('/auth/me', headers=auth_header(access_token)).json()

    assert 'search_daily_limit' not in body
