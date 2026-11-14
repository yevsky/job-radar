from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobOffer, Technology
from app.models.enums import EmploymentType, ExperienceLevel, SourceKind
from tests.helpers import auth_header, make_offer

URL = '/job-offers'
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def filter_offers(db: Session) -> None:
    """Four active offers with different technologies, locations, levels and types."""
    python = Technology(name='Python')
    docker = Technology(name='Docker')
    java = Technology(name='Java')
    db.add_all(
        [
            make_offer(
                url='https://example.com/python-wroclaw',
                title='Python Wroclaw',
                location='Wrocław, PL',
                experience_level=ExperienceLevel.JUNIOR,
                employment_type=EmploymentType.B2B,
                technologies=[python, docker],
            ),
            make_offer(
                url='https://example.com/python-remote',
                title='Python Remote',
                location='Remote',
                experience_level=ExperienceLevel.SENIOR,
                employment_type=EmploymentType.FULL_TIME,
                technologies=[python],
            ),
            make_offer(
                url='https://example.com/java-krakow',
                title='Java Krakow',
                location='Kraków, PL',
                experience_level=ExperienceLevel.MIDDLE,
                employment_type=EmploymentType.B2B,
                technologies=[java, docker],
            ),
            make_offer(
                url='https://example.com/no-details',
                title='No Details',
            ),
        ]
    )
    db.flush()


def filtered_titles(
    api: TestClient, token: str, params: Mapping[str, str | list[str]]
) -> list[str]:
    """Call the list with filters and return the matching titles, sorted."""
    response = api.get(URL, params=params, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['total'] == len(body['items'])
    return sorted(titles(body))


def add_offers(db: Session, count: int) -> list[JobOffer]:
    """Add `count` active offers; offer i is i hours older than offer 0 (offer 0 is newest)."""
    offers = [
        make_offer(
            url=f'https://example.com/jobs/{i}',
            title=f'Offer {i}',
            created_at=NOW - timedelta(hours=i),
        )
        for i in range(count)
    ]
    db.add_all(offers)
    db.flush()
    return offers


def titles(body: dict[str, object]) -> list[str]:
    items = body['items']
    assert isinstance(items, list)
    return [item['title'] for item in items]


def test_list_without_token_returns_401(api: TestClient) -> None:
    response = api.get(URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_with_no_offers_returns_empty_page(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'items': [], 'total': 0, 'limit': 20, 'offset': 0}


def test_list_returns_offer_fields_and_sorted_technology_names(
    api: TestClient, access_token: str, db: Session
) -> None:
    offer = make_offer(
        title='Python Developer',
        company_name='Codesky',
        location='Wrocław',
        employment_type=EmploymentType.B2B,
        experience_level=ExperienceLevel.JUNIOR,
        deadline=datetime(2026, 12, 31, tzinfo=UTC),
        technologies=[Technology(name='Python'), Technology(name='Docker')],
    )
    db.add(offer)
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['total'] == 1
    item = body['items'][0]
    assert item['id'] == offer.id
    assert item['title'] == 'Python Developer'
    assert item['company_name'] == 'Codesky'
    assert item['location'] == 'Wrocław'
    assert item['employment_type'] == 'b2b'
    assert item['experience_level'] == 'junior'
    assert item['deadline'].startswith('2026-12-31')
    assert item['technologies'] == ['Docker', 'Python']


def test_list_shows_newest_offers_first(api: TestClient, access_token: str, db: Session) -> None:
    oldest = make_offer(url='https://example.com/old', title='Old', created_at=NOW)
    newest = make_offer(
        url='https://example.com/new', title='New', created_at=NOW + timedelta(days=1)
    )
    db.add_all([oldest, newest])
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    assert titles(response.json()) == ['New', 'Old']


def test_offers_with_same_created_at_are_ordered_by_id(
    api: TestClient, access_token: str, db: Session
) -> None:
    first = make_offer(url='https://example.com/a', title='First', created_at=NOW)
    second = make_offer(url='https://example.com/b', title='Second', created_at=NOW)
    db.add(first)
    db.flush()
    db.add(second)
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    assert titles(response.json()) == ['Second', 'First']


def test_inactive_offers_are_not_listed_or_counted(
    api: TestClient, access_token: str, db: Session
) -> None:
    db.add_all(
        [
            make_offer(url='https://example.com/active', title='Active'),
            make_offer(url='https://example.com/closed', title='Closed', is_active=False),
        ]
    )
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    body = response.json()
    assert titles(body) == ['Active']
    assert body['total'] == 1


def test_limit_returns_first_page_and_total_counts_all(
    api: TestClient, access_token: str, db: Session
) -> None:
    add_offers(db, 3)

    response = api.get(URL, params={'limit': 2}, headers=auth_header(access_token))

    body = response.json()
    assert titles(body) == ['Offer 0', 'Offer 1']
    assert body['total'] == 3
    assert body['limit'] == 2
    assert body['offset'] == 0


def test_offset_returns_next_page(api: TestClient, access_token: str, db: Session) -> None:
    add_offers(db, 3)

    response = api.get(URL, params={'limit': 2, 'offset': 2}, headers=auth_header(access_token))

    body = response.json()
    assert titles(body) == ['Offer 2']
    assert body['total'] == 3
    assert body['offset'] == 2


def test_offset_past_the_end_returns_empty_items(
    api: TestClient, access_token: str, db: Session
) -> None:
    add_offers(db, 2)

    response = api.get(URL, params={'offset': 10}, headers=auth_header(access_token))

    body = response.json()
    assert body['items'] == []
    assert body['total'] == 2


@pytest.mark.parametrize(
    'params',
    [
        {'limit': 0},
        {'limit': 101},
        {'offset': -1},
        {'limit': 'abc'},
    ],
)
def test_invalid_pagination_returns_422(
    api: TestClient, access_token: str, params: dict[str, int | str]
) -> None:
    response = api.get(URL, params=params, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_limit_100_is_allowed(api: TestClient, access_token: str) -> None:
    response = api.get(URL, params={'limit': 100}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK


def test_details_without_token_returns_401(api: TestClient, db: Session) -> None:
    offer = make_offer()
    db.add(offer)
    db.flush()

    response = api.get(f'{URL}/{offer.id}')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_details_returns_all_fields(api: TestClient, access_token: str, db: Session) -> None:
    offer = make_offer(
        url='https://example.com/jobs/python',
        title='Python Developer',
        location='Remote',
        employment_type=EmploymentType.FULL_TIME,
        experience_level=ExperienceLevel.MIDDLE,
        source=SourceKind.SEARCH,
        deadline=datetime(2026, 12, 31, tzinfo=UTC),
        last_seen_at=NOW,
        created_at=NOW - timedelta(days=1),
        technologies=[Technology(name='FastAPI'), Technology(name='Docker')],
    )
    db.add(offer)
    db.flush()

    response = api.get(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert set(body) == {
        'id',
        'title',
        'company_name',
        'location',
        'employment_type',
        'experience_level',
        'deadline',
        'technologies',
        'source',
        'url',
        'is_active',
        'last_seen_at',
        'created_at',
    }
    assert body['id'] == offer.id
    assert body['title'] == 'Python Developer'
    assert body['location'] == 'Remote'
    assert body['employment_type'] == 'full_time'
    assert body['experience_level'] == 'middle'
    assert body['source'] == 'search'
    assert body['url'] == 'https://example.com/jobs/python'
    assert body['is_active'] is True
    assert body['deadline'].startswith('2026-12-31')
    assert body['last_seen_at'].startswith('2026-11-01')
    assert body['created_at'].startswith('2026-10-31')
    assert body['technologies'] == ['Docker', 'FastAPI']


def test_details_of_offer_with_only_required_fields_has_nulls(
    api: TestClient, access_token: str, db: Session
) -> None:
    offer = make_offer()
    db.add(offer)
    db.flush()

    response = api.get(f'{URL}/{offer.id}', headers=auth_header(access_token))

    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    for field in ('location', 'employment_type', 'experience_level', 'deadline', 'last_seen_at'):
        assert body[field] is None
    assert body['technologies'] == []


def test_details_of_inactive_offer_still_works(
    api: TestClient, access_token: str, db: Session
) -> None:
    offer = make_offer(is_active=False)
    db.add(offer)
    db.flush()

    response = api.get(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['is_active'] is False


def test_details_of_unknown_offer_returns_404(api: TestClient, access_token: str) -> None:
    response = api.get(f'{URL}/999999', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {'detail': 'Job offer not found'}


def test_details_with_non_integer_id_returns_422(api: TestClient, access_token: str) -> None:
    response = api.get(f'{URL}/abc', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.usefixtures('filter_offers')
def test_no_filters_returns_all_offers(api: TestClient, access_token: str) -> None:
    assert filtered_titles(api, access_token, {}) == [
        'Java Krakow',
        'No Details',
        'Python Remote',
        'Python Wroclaw',
    ]


@pytest.mark.usefixtures('filter_offers')
@pytest.mark.parametrize('name', ['python', 'PYTHON', 'Python'])
def test_filter_by_technology_ignores_case(api: TestClient, access_token: str, name: str) -> None:
    assert filtered_titles(api, access_token, {'technology': name}) == [
        'Python Remote',
        'Python Wroclaw',
    ]


@pytest.mark.usefixtures('filter_offers')
def test_filter_by_several_technologies_requires_all(api: TestClient, access_token: str) -> None:
    params = {'technology': ['python', 'docker']}

    assert filtered_titles(api, access_token, params) == ['Python Wroclaw']


@pytest.mark.usefixtures('filter_offers')
def test_filter_by_unknown_technology_returns_empty_page(
    api: TestClient, access_token: str
) -> None:
    response = api.get(URL, params={'technology': 'cobol'}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'items': [], 'total': 0, 'limit': 20, 'offset': 0}


@pytest.mark.usefixtures('filter_offers')
@pytest.mark.parametrize(
    ('location', 'expected'),
    [
        ('WROC', ['Python Wroclaw']),
        ('remote', ['Python Remote']),
        (', pl', ['Java Krakow', 'Python Wroclaw']),
        ('berlin', []),
    ],
)
def test_filter_by_location_matches_part_of_it_ignoring_case(
    api: TestClient, access_token: str, location: str, expected: list[str]
) -> None:
    assert filtered_titles(api, access_token, {'location': location}) == expected


@pytest.mark.usefixtures('filter_offers')
@pytest.mark.parametrize('location', ['%', '_'])
def test_location_wildcard_characters_are_matched_literally(
    api: TestClient, access_token: str, location: str
) -> None:
    assert filtered_titles(api, access_token, {'location': location}) == []


@pytest.mark.usefixtures('filter_offers')
def test_filter_by_experience_level(api: TestClient, access_token: str) -> None:
    assert filtered_titles(api, access_token, {'experience_level': 'junior'}) == ['Python Wroclaw']


@pytest.mark.usefixtures('filter_offers')
def test_several_experience_levels_match_any_of_them(api: TestClient, access_token: str) -> None:
    params = {'experience_level': ['junior', 'senior']}

    assert filtered_titles(api, access_token, params) == ['Python Remote', 'Python Wroclaw']


@pytest.mark.usefixtures('filter_offers')
def test_filter_by_employment_type(api: TestClient, access_token: str) -> None:
    assert filtered_titles(api, access_token, {'employment_type': 'b2b'}) == [
        'Java Krakow',
        'Python Wroclaw',
    ]


@pytest.mark.usefixtures('filter_offers')
def test_several_employment_types_match_any_of_them(api: TestClient, access_token: str) -> None:
    params = {'employment_type': ['b2b', 'full_time']}

    assert filtered_titles(api, access_token, params) == [
        'Java Krakow',
        'Python Remote',
        'Python Wroclaw',
    ]


@pytest.mark.usefixtures('filter_offers')
@pytest.mark.parametrize(
    ('params', 'expected'),
    [
        ({'technology': 'docker', 'employment_type': 'b2b'}, ['Java Krakow', 'Python Wroclaw']),
        ({'technology': 'docker', 'location': 'krak'}, ['Java Krakow']),
        ({'technology': 'python', 'experience_level': 'middle'}, []),
        (
            {
                'technology': 'python',
                'location': 'wroc',
                'experience_level': 'junior',
                'employment_type': 'b2b',
            },
            ['Python Wroclaw'],
        ),
    ],
)
def test_filters_combine_with_and(
    api: TestClient,
    access_token: str,
    params: dict[str, str | list[str]],
    expected: list[str],
) -> None:
    assert filtered_titles(api, access_token, params) == expected


@pytest.mark.usefixtures('filter_offers')
def test_inactive_offers_are_hidden_even_when_they_match(
    api: TestClient, access_token: str, db: Session
) -> None:
    db.add(
        make_offer(
            url='https://example.com/closed-rust',
            title='Closed Rust',
            is_active=False,
            technologies=[Technology(name='Rust')],
        )
    )
    db.flush()

    assert filtered_titles(api, access_token, {'technology': 'rust'}) == []


@pytest.mark.usefixtures('filter_offers')
def test_total_counts_filtered_offers_across_pages(api: TestClient, access_token: str) -> None:
    params = {'employment_type': 'b2b', 'limit': '1'}

    response = api.get(URL, params=params, headers=auth_header(access_token))

    body = response.json()
    assert len(body['items']) == 1
    assert body['total'] == 2


@pytest.mark.parametrize(
    'params',
    [
        {'experience_level': 'mid'},
        {'employment_type': 'freelance'},
        {'location': 'x' * 101},
    ],
)
def test_invalid_filter_values_return_422(
    api: TestClient, access_token: str, params: dict[str, str]
) -> None:
    response = api.get(URL, params=params, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
