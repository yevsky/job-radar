import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Technology, UserProfile
from tests.conftest import register_and_login
from tests.helpers import auth_header

FULL_PROFILE = {
    'first_name': 'John',
    'last_name': 'Example',
    'bio': 'Backend developer learning FastAPI.',
    'experience_level': 'junior',
    'desired_position': 'backend developer',
}
LOCATIONS_URL = '/profile/me/locations'
EMPLOYMENT_TYPES_URL = '/profile/me/employment-types'
SKILLS_URL = '/profile/me/skills'


@pytest.mark.parametrize('method', ['get', 'put'])
def test_profile_without_token_returns_401(api: TestClient, method: str) -> None:
    response = api.request(method, '/profile/me', json={})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_profile_for_new_user_returns_empty_profile(api: TestClient, access_token: str) -> None:
    response = api.get('/profile/me', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        'first_name': None,
        'last_name': None,
        'bio': None,
        'experience_level': None,
        'desired_position': None,
        'preferred_locations': [],
        'preferred_employment_types': [],
        'skills': [],
    }


def test_put_then_get_returns_saved_profile(api: TestClient, access_token: str) -> None:
    put_response = api.put('/profile/me', json=FULL_PROFILE, headers=auth_header(access_token))
    get_response = api.get('/profile/me', headers=auth_header(access_token))

    assert put_response.status_code == status.HTTP_200_OK
    assert get_response.status_code == status.HTTP_200_OK
    for body in (put_response.json(), get_response.json()):
        for field, value in FULL_PROFILE.items():
            assert body[field] == value


def test_second_put_updates_existing_profile(
    api: TestClient, access_token: str, db: Session
) -> None:
    api.put('/profile/me', json=FULL_PROFILE, headers=auth_header(access_token))
    response = api.put(
        '/profile/me',
        json={**FULL_PROFILE, 'first_name': 'Changed'},
        headers=auth_header(access_token),
    )

    assert response.json()['first_name'] == 'Changed'
    assert len(db.scalars(select(UserProfile)).all()) == 1


def test_put_replaces_whole_profile(api: TestClient, access_token: str) -> None:
    api.put('/profile/me', json=FULL_PROFILE, headers=auth_header(access_token))
    response = api.put(
        '/profile/me', json={'first_name': 'Yevhen'}, headers=auth_header(access_token)
    )

    body = response.json()
    assert body['first_name'] == 'Yevhen'
    assert body['bio'] is None
    assert body['experience_level'] is None


def test_put_trims_whitespace(api: TestClient, access_token: str) -> None:
    response = api.put(
        '/profile/me', json={'first_name': '  Yevhen  '}, headers=auth_header(access_token)
    )

    assert response.json()['first_name'] == 'Yevhen'


@pytest.mark.parametrize(
    'payload',
    [
        {'experience_level': 'wizard'},
        {'first_name': 'a' * 121},
        {'last_name': 'a' * 121},
        {'desired_position': 'a' * 121},
        {'bio': 'a' * 2001},
    ],
)
def test_put_with_invalid_data_returns_422(
    api: TestClient, access_token: str, payload: dict[str, str]
) -> None:
    response = api.put('/profile/me', json=payload, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_users_only_see_their_own_profile(api: TestClient, access_token: str) -> None:
    _, other_token = register_and_login(api, 'other@example.com')

    api.put('/profile/me', json=FULL_PROFILE, headers=auth_header(access_token))
    response = api.get('/profile/me', headers=auth_header(other_token))

    assert response.json()['first_name'] is None


def test_locations_without_token_returns_401(api: TestClient) -> None:
    response = api.put(LOCATIONS_URL, json={'locations': ['Remote']})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_put_locations_then_get_returns_them(api: TestClient, access_token: str) -> None:
    put_response = api.put(
        LOCATIONS_URL, json={'locations': ['Wroclaw', 'Remote']}, headers=auth_header(access_token)
    )
    get_response = api.get('/profile/me', headers=auth_header(access_token))

    assert put_response.status_code == status.HTTP_200_OK
    for body in (put_response.json(), get_response.json()):
        assert sorted(body['preferred_locations']) == ['Remote', 'Wroclaw']


def test_second_put_locations_replaces_the_list(api: TestClient, access_token: str) -> None:
    api.put(
        LOCATIONS_URL, json={'locations': ['Wroclaw', 'Remote']}, headers=auth_header(access_token)
    )
    response = api.put(
        LOCATIONS_URL, json={'locations': ['Krakow']}, headers=auth_header(access_token)
    )

    assert response.json()['preferred_locations'] == ['Krakow']


def test_put_empty_locations_clears_the_list(api: TestClient, access_token: str) -> None:
    api.put(
        LOCATIONS_URL, json={'locations': ['Wroclaw', 'Remote']}, headers=auth_header(access_token)
    )
    response = api.put(LOCATIONS_URL, json={'locations': []}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['preferred_locations'] == []


def test_put_locations_removes_case_insensitive_duplicates(
    api: TestClient, access_token: str
) -> None:
    response = api.put(
        LOCATIONS_URL,
        json={'locations': ['Wroclaw', 'wroclaw', ' WROCLAW ']},
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['preferred_locations'] == ['Wroclaw']


@pytest.mark.parametrize(
    'locations',
    [
        [''],
        ['   '],
        ['a' * 101],
        [f'City {i}' for i in range(11)],
    ],
    ids=['empty', 'whitespace', 'too-long', 'too-many'],
)
def test_put_invalid_locations_returns_422(
    api: TestClient, access_token: str, locations: list[str]
) -> None:
    response = api.put(
        LOCATIONS_URL, json={'locations': locations}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_put_locations_keeps_profile_fields(api: TestClient, access_token: str) -> None:
    api.put('/profile/me', json=FULL_PROFILE, headers=auth_header(access_token))
    response = api.put(
        LOCATIONS_URL, json={'locations': ['Remote']}, headers=auth_header(access_token)
    )

    body = response.json()
    assert body['preferred_locations'] == ['Remote']
    assert body['first_name'] == FULL_PROFILE['first_name']
    assert body['desired_position'] == FULL_PROFILE['desired_position']


def test_employment_types_without_token_returns_401(api: TestClient) -> None:
    response = api.put(EMPLOYMENT_TYPES_URL, json={'employment_types': ['b2b']})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_put_employment_types_then_get_returns_them(api: TestClient, access_token: str) -> None:
    put_response = api.put(
        EMPLOYMENT_TYPES_URL,
        json={'employment_types': ['full_time', 'b2b']},
        headers=auth_header(access_token),
    )
    get_response = api.get('/profile/me', headers=auth_header(access_token))

    assert put_response.status_code == status.HTTP_200_OK
    for body in (put_response.json(), get_response.json()):
        assert sorted(body['preferred_employment_types']) == ['b2b', 'full_time']


def test_second_put_employment_types_replaces_the_list(api: TestClient, access_token: str) -> None:
    api.put(
        EMPLOYMENT_TYPES_URL,
        json={'employment_types': ['full_time', 'b2b']},
        headers=auth_header(access_token),
    )
    response = api.put(
        EMPLOYMENT_TYPES_URL,
        json={'employment_types': ['contract']},
        headers=auth_header(access_token),
    )

    assert response.json()['preferred_employment_types'] == ['contract']


def test_put_empty_employment_types_clears_the_list(api: TestClient, access_token: str) -> None:
    api.put(
        EMPLOYMENT_TYPES_URL,
        json={'employment_types': ['full_time', 'b2b']},
        headers=auth_header(access_token),
    )
    response = api.put(
        EMPLOYMENT_TYPES_URL, json={'employment_types': []}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['preferred_employment_types'] == []


def test_put_employment_types_stores_duplicates_once(api: TestClient, access_token: str) -> None:
    response = api.put(
        EMPLOYMENT_TYPES_URL,
        json={'employment_types': ['b2b', 'b2b', 'full_time']},
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert sorted(response.json()['preferred_employment_types']) == ['b2b', 'full_time']


@pytest.mark.parametrize(
    'value',
    ['freelance', 'B2B', '', 5],
    ids=['unknown', 'wrong-case', 'empty', 'not-a-string'],
)
def test_put_invalid_employment_type_returns_422(
    api: TestClient, access_token: str, value: str | int
) -> None:
    response = api.put(
        EMPLOYMENT_TYPES_URL, json={'employment_types': [value]}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_put_employment_types_keeps_locations(api: TestClient, access_token: str) -> None:
    api.put(LOCATIONS_URL, json={'locations': ['Remote']}, headers=auth_header(access_token))
    response = api.put(
        EMPLOYMENT_TYPES_URL, json={'employment_types': ['b2b']}, headers=auth_header(access_token)
    )

    body = response.json()
    assert body['preferred_employment_types'] == ['b2b']
    assert body['preferred_locations'] == ['Remote']


def technology_names(db: Session) -> list[str]:
    return sorted(db.scalars(select(Technology.name)).all())


def test_skills_without_token_returns_401(api: TestClient) -> None:
    response = api.put(SKILLS_URL, json={'skills': ['Python']})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_put_skills_creates_missing_technologies(
    api: TestClient, access_token: str, db: Session
) -> None:
    put_response = api.put(
        SKILLS_URL, json={'skills': ['Python', 'FastAPI']}, headers=auth_header(access_token)
    )
    get_response = api.get('/profile/me', headers=auth_header(access_token))

    assert put_response.status_code == status.HTTP_200_OK
    for body in (put_response.json(), get_response.json()):
        assert sorted(body['skills']) == ['FastAPI', 'Python']
    assert technology_names(db) == ['FastAPI', 'Python']


def test_put_skills_reuses_existing_technology_ignoring_case(
    api: TestClient, access_token: str, db: Session
) -> None:
    api.put(SKILLS_URL, json={'skills': ['Python']}, headers=auth_header(access_token))
    response = api.put(SKILLS_URL, json={'skills': ['python']}, headers=auth_header(access_token))

    assert response.json()['skills'] == ['Python']
    assert technology_names(db) == ['Python']


def test_users_share_the_same_technology(api: TestClient, access_token: str, db: Session) -> None:
    _, other_token = register_and_login(api, 'other@example.com')

    api.put(SKILLS_URL, json={'skills': ['Python']}, headers=auth_header(access_token))
    response = api.put(SKILLS_URL, json={'skills': ['python']}, headers=auth_header(other_token))

    assert response.json()['skills'] == ['Python']
    assert technology_names(db) == ['Python']


def test_second_put_skills_replaces_the_list(api: TestClient, access_token: str) -> None:
    api.put(SKILLS_URL, json={'skills': ['Python', 'FastAPI']}, headers=auth_header(access_token))
    response = api.put(SKILLS_URL, json={'skills': ['Docker']}, headers=auth_header(access_token))

    assert response.json()['skills'] == ['Docker']


def test_put_empty_skills_clears_the_list(api: TestClient, access_token: str) -> None:
    api.put(SKILLS_URL, json={'skills': ['Python', 'FastAPI']}, headers=auth_header(access_token))
    response = api.put(SKILLS_URL, json={'skills': []}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['skills'] == []


def test_removing_a_skill_keeps_the_technology(
    api: TestClient, access_token: str, db: Session
) -> None:
    api.put(SKILLS_URL, json={'skills': ['Python']}, headers=auth_header(access_token))
    response = api.put(SKILLS_URL, json={'skills': []}, headers=auth_header(access_token))

    assert response.json()['skills'] == []
    assert technology_names(db) == ['Python']


def test_put_skills_removes_case_insensitive_duplicates(
    api: TestClient, access_token: str, db: Session
) -> None:
    response = api.put(
        SKILLS_URL,
        json={'skills': ['Python', 'python', ' PYTHON ']},
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['skills'] == ['Python']
    assert technology_names(db) == ['Python']


@pytest.mark.parametrize(
    'skills',
    [
        [''],
        ['   '],
        ['a' * 51],
        [f'Tech {i}' for i in range(51)],
    ],
    ids=['empty', 'whitespace', 'too-long', 'too-many'],
)
def test_put_invalid_skills_returns_422(
    api: TestClient, access_token: str, skills: list[str]
) -> None:
    response = api.put(SKILLS_URL, json={'skills': skills}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
