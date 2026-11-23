"""PATCH /admin/users/{id}/role and DELETE /admin/users/{id}."""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, JobOffer, User, UserProfile
from app.models.enums import ApplicationStatus
from tests.conftest import register_and_login
from tests.helpers import ADMIN_EMAIL, USER_EMAIL, auth_header, make_offer


def admin_id(api: TestClient, admin_token: str) -> int:
    return int(api.get('/auth/me', headers=auth_header(admin_token)).json()['id'])


# role in the user list and /auth/me


def test_user_list_shows_each_role_by_name(
    api: TestClient, admin_token: str, registered_user_id: int
) -> None:
    del registered_user_id

    users = api.get('/admin/users', headers=auth_header(admin_token)).json()

    assert {user['email']: user['role'] for user in users} == {
        USER_EMAIL: 'user',
        ADMIN_EMAIL: 'admin',
    }


def test_auth_me_shows_the_role(api: TestClient, access_token: str) -> None:
    body = api.get('/auth/me', headers=auth_header(access_token)).json()

    assert body['role'] == 'user'


# PATCH /admin/users/{id}/role


def test_admin_makes_a_user_an_admin(
    api: TestClient, admin_token: str, registered_user_id: int
) -> None:
    response = api.patch(
        f'/admin/users/{registered_user_id}/role',
        json={'role': 'admin'},
        headers=auth_header(admin_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['role'] == 'admin'
    assert response.json()['email'] == USER_EMAIL


def test_new_admin_can_open_admin_pages_at_once(
    api: TestClient, admin_token: str, registered_user_id: int, access_token: str
) -> None:
    """The role is read from the database on every request, so no new login is needed."""
    api.patch(
        f'/admin/users/{registered_user_id}/role',
        json={'role': 'admin'},
        headers=auth_header(admin_token),
    )

    response = api.get('/admin/users', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK


def test_admin_turns_an_admin_back_into_a_user(api: TestClient, admin_token: str) -> None:
    other_id, other_token = register_and_login(api, 'other@example.com')
    api.patch(
        f'/admin/users/{other_id}/role', json={'role': 'admin'}, headers=auth_header(admin_token)
    )

    response = api.patch(
        f'/admin/users/{other_id}/role', json={'role': 'user'}, headers=auth_header(admin_token)
    )

    assert response.json()['role'] == 'user'
    forbidden = api.get('/admin/users', headers=auth_header(other_token))
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN


def test_admin_cannot_change_their_own_role(api: TestClient, admin_token: str) -> None:
    own_id = admin_id(api, admin_token)

    response = api.patch(
        f'/admin/users/{own_id}/role', json={'role': 'user'}, headers=auth_header(admin_token)
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert api.get('/auth/me', headers=auth_header(admin_token)).json()['role'] == 'admin'


def test_unknown_role_returns_422(
    api: TestClient, admin_token: str, registered_user_id: int
) -> None:
    response = api.patch(
        f'/admin/users/{registered_user_id}/role',
        json={'role': 'owner'},
        headers=auth_header(admin_token),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_changing_the_role_of_a_missing_user_returns_404(api: TestClient, admin_token: str) -> None:
    response = api.patch(
        '/admin/users/999999/role', json={'role': 'admin'}, headers=auth_header(admin_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_normal_user_cannot_change_roles(
    api: TestClient, access_token: str, registered_user_id: int
) -> None:
    response = api.patch(
        f'/admin/users/{registered_user_id}/role',
        json={'role': 'admin'},
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# DELETE /admin/users/{id}


def test_admin_deletes_a_user(api: TestClient, admin_token: str, registered_user_id: int) -> None:
    response = api.delete(f'/admin/users/{registered_user_id}', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    emails = [
        user['email'] for user in api.get('/admin/users', headers=auth_header(admin_token)).json()
    ]
    assert emails == [ADMIN_EMAIL]


def test_deleted_users_token_stops_working(
    api: TestClient, admin_token: str, registered_user_id: int, access_token: str
) -> None:
    api.delete(f'/admin/users/{registered_user_id}', headers=auth_header(admin_token))

    response = api.get('/auth/me', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_deleting_a_user_deletes_their_data_but_keeps_public_offers(
    api: TestClient, admin_token: str, registered_user_id: int, db: Session
) -> None:
    public = make_offer('https://example.com/public')
    private = make_offer('https://example.com/private', owner_id=registered_user_id)
    db.add_all([public, private, UserProfile(user_id=registered_user_id, first_name='Ola')])
    db.flush()
    db.add(
        Application(
            user_id=registered_user_id, job_offer_id=public.id, status=ApplicationStatus.SAVED
        )
    )
    db.flush()

    api.delete(f'/admin/users/{registered_user_id}', headers=auth_header(admin_token))

    db.expire_all()
    assert db.get(User, registered_user_id) is None
    assert db.scalar(select(func.count()).select_from(Application)) == 0
    assert db.scalar(select(func.count()).select_from(UserProfile)) == 0
    assert db.scalars(select(JobOffer.url)).all() == ['https://example.com/public']


def test_admin_cannot_delete_their_own_account(api: TestClient, admin_token: str) -> None:
    response = api.delete(
        f'/admin/users/{admin_id(api, admin_token)}', headers=auth_header(admin_token)
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_deleting_a_missing_user_returns_404(api: TestClient, admin_token: str) -> None:
    response = api.delete('/admin/users/999999', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_normal_user_cannot_delete_users(
    api: TestClient, access_token: str, registered_user_id: int
) -> None:
    response = api.delete(f'/admin/users/{registered_user_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN
