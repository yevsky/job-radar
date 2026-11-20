from fastapi import status
from fastapi.testclient import TestClient

from app.schemas.search import SearchQuery
from tests.helpers import USER_EMAIL, auth_header

URL = '/search/defaults'
EMPTY_FORM: dict[str, object] = {
    'position': None,
    'locations': [],
    'country': 'pl',
    'posted_within': None,
    'page': 1,
}


def fill_profile(api: TestClient, token: str, **lists: list[str]) -> None:
    """Save a full profile, then whichever of locations / skills / employment types are given."""
    profile = {
        'first_name': 'John',
        'last_name': 'Example',
        'bio': 'Secret bio text',
        'experience_level': 'junior',
        'desired_position': 'Python developer',
    }
    headers = auth_header(token)
    assert api.put('/profile/me', json=profile, headers=headers).status_code == status.HTTP_200_OK
    urls = {
        'locations': '/profile/me/locations',
        'skills': '/profile/me/skills',
        'employment_types': '/profile/me/employment-types',
    }
    for field, values in lists.items():
        response = api.put(urls[field], json={field: values}, headers=headers)
        assert response.status_code == status.HTTP_200_OK


def test_defaults_without_token_returns_401(api: TestClient) -> None:
    assert api.get(URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_user_without_profile_gets_empty_form(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == EMPTY_FORM


def test_full_profile_fills_the_form(api: TestClient, access_token: str) -> None:
    fill_profile(
        api,
        access_token,
        locations=['Wrocław', 'Remote'],
        skills=['Python', 'FastAPI'],
        employment_types=['b2b', 'full_time'],
    )

    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['position'] == 'Junior Python developer'  # the profile's level goes in front
    assert sorted(body['locations']) == ['Remote', 'Wrocław']
    assert body['country'] == 'pl'
    assert body['posted_within'] is None
    assert 'skills' not in body  # skills and contract types are not search filters any more


def test_level_is_not_added_twice(api: TestClient, access_token: str) -> None:
    fill_profile(api, access_token)
    api.put(
        '/profile/me',
        json={'desired_position': 'Senior Python developer', 'experience_level': 'junior'},
        headers=auth_header(access_token),
    )

    body = api.get(URL, headers=auth_header(access_token)).json()

    assert body['position'] == 'Senior Python developer'  # the user's own words win


def test_form_takes_at_most_5_locations(api: TestClient, access_token: str) -> None:
    locations = [f'City {n}' for n in range(7)]
    fill_profile(api, access_token, locations=locations)

    body = api.get(URL, headers=auth_header(access_token)).json()

    assert len(body['locations']) == 5
    assert set(body['locations']) <= set(locations)


def test_long_profile_location_fits_in_the_form(api: TestClient, access_token: str) -> None:
    long_location = 'L' * 100  # the longest location a profile accepts
    fill_profile(api, access_token, locations=[long_location])

    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['locations'] == [long_location]


def test_form_has_no_personal_data(api: TestClient, access_token: str) -> None:
    fill_profile(api, access_token, skills=['Python'])

    response = api.get(URL, headers=auth_header(access_token))

    assert set(response.json()) == set(SearchQuery.model_fields)
    for private in ('John', 'Example', 'Secret bio text', USER_EMAIL):
        assert private not in response.text


def test_form_can_be_sent_back_unchanged(api: TestClient, access_token: str) -> None:
    fill_profile(api, access_token, skills=['Python'], locations=['Kraków'])

    body = api.get(URL, headers=auth_header(access_token)).json()

    assert SearchQuery.model_validate(body).text() == 'Junior Python developer Kraków'
