from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_search_sources
from app.main import app
from app.models import SearchRun, User
from app.schemas.job_offer import JobOfferImport
from app.search_sources.fake import FakeSearchSource
from tests.conftest import register_and_login
from tests.helpers import auth_header

URL = '/search'
FORM = {'position': 'Python developer'}
OTHER_EMAIL = 'other@example.com'


@pytest.fixture
def source(api: TestClient) -> FakeSearchSource:
    """One fake source with one result, used by POST /search in every test of this file."""
    del api  # requested only for its cleanup of dependency_overrides
    fake = FakeSearchSource(
        results=[
            JobOfferImport.model_validate(
                {'title': 'Dev', 'company_name': 'Codesky', 'url': 'https://example.com/1'}
            )
        ]
    )
    app.dependency_overrides[get_search_sources] = lambda: [fake]
    return fake


@pytest.fixture
def limit_of(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], None]:
    """Change the default daily limit for one test."""

    def set_limit(limit: int) -> None:
        monkeypatch.setattr('app.services.search.settings.search_daily_limit', limit)

    return set_limit


def search(api: TestClient, token: str) -> int:
    return api.post(URL, json=FORM, headers=auth_header(token)).status_code


def test_searches_stop_at_the_daily_limit(
    api: TestClient,
    access_token: str,
    source: FakeSearchSource,
    limit_of: Callable[[int], None],
) -> None:
    limit_of(2)

    first = api.post(URL, json=FORM, headers=auth_header(access_token))
    second = api.post(URL, json=FORM, headers=auth_header(access_token))
    third = api.post(URL, json=FORM, headers=auth_header(access_token))

    assert first.status_code == status.HTTP_200_OK
    assert first.json()['searches_left_today'] == 1
    assert second.status_code == status.HTTP_200_OK
    assert second.json()['searches_left_today'] == 0
    assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert third.json()['detail'] == 'Daily search limit reached, try again tomorrow'
    assert len(source.queries) == 2  # the third search never reached the source


def test_each_search_stores_one_run_without_results(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    source: FakeSearchSource,
    db: Session,
) -> None:
    del source
    search(api, access_token)

    runs = db.scalars(select(SearchRun).where(SearchRun.user_id == registered_user_id)).all()
    assert len(runs) == 1
    assert runs[0].result_count == 1
    assert runs[0].created_at is not None


def test_empty_form_does_not_count(
    api: TestClient, access_token: str, source: FakeSearchSource, db: Session
) -> None:
    del source
    response = api.post(URL, json={}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert db.scalar(select(func.count()).select_from(SearchRun)) == 0


def test_searches_from_yesterday_do_not_count(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    source: FakeSearchSource,
    limit_of: Callable[[int], None],
    db: Session,
) -> None:
    del source
    limit_of(1)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    db.add(SearchRun(user_id=registered_user_id, result_count=3, created_at=yesterday))
    db.flush()

    assert search(api, access_token) == status.HTTP_200_OK


def test_one_users_searches_do_not_use_up_another_users_limit(
    api: TestClient,
    access_token: str,
    source: FakeSearchSource,
    limit_of: Callable[[int], None],
) -> None:
    del source
    limit_of(1)
    _, other_token = register_and_login(api, OTHER_EMAIL)

    assert search(api, access_token) == status.HTTP_200_OK
    assert search(api, access_token) == status.HTTP_429_TOO_MANY_REQUESTS
    assert search(api, other_token) == status.HTTP_200_OK


def test_deleting_a_user_deletes_their_runs(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    source: FakeSearchSource,
    db: Session,
) -> None:
    del source
    search(api, access_token)
    user = db.get(User, registered_user_id)
    assert user is not None

    db.delete(user)
    db.flush()

    count = db.scalar(select(func.count()).select_from(SearchRun))
    assert count == 0


# GET /search/usage


def test_usage_shows_limit_and_what_is_left(
    api: TestClient, access_token: str, source: FakeSearchSource, limit_of: Callable[[int], None]
) -> None:
    del source
    limit_of(5)
    search(api, access_token)

    response = api.get('/search/usage', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'daily_limit': 5, 'used_today': 1, 'left_today': 4}


def test_usage_without_token_returns_401(api: TestClient) -> None:
    assert api.get('/search/usage').status_code == status.HTTP_401_UNAUTHORIZED


# PUT /admin/users/{id}/search-limit


def limit_url(user_id: int) -> str:
    return f'/admin/users/{user_id}/search-limit'


def test_admin_gives_a_user_their_own_limit(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    admin_token: str,
    source: FakeSearchSource,
    limit_of: Callable[[int], None],
) -> None:
    del source
    limit_of(10)

    response = api.put(
        limit_url(registered_user_id),
        json={'search_daily_limit': 1},
        headers=auth_header(admin_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        'user_id': registered_user_id,
        'search_daily_limit': 1,
        'effective_limit': 1,
    }
    assert search(api, access_token) == status.HTTP_200_OK
    assert search(api, access_token) == status.HTTP_429_TOO_MANY_REQUESTS


def test_admin_can_raise_a_limit_above_the_default(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    admin_token: str,
    source: FakeSearchSource,
    limit_of: Callable[[int], None],
) -> None:
    del source
    limit_of(1)
    api.put(
        limit_url(registered_user_id),
        json={'search_daily_limit': 3},
        headers=auth_header(admin_token),
    )

    assert [search(api, access_token) for _ in range(4)] == [200, 200, 200, 429]


def test_null_goes_back_to_the_default(
    api: TestClient,
    registered_user_id: int,
    admin_token: str,
    limit_of: Callable[[int], None],
) -> None:
    limit_of(7)
    headers = auth_header(admin_token)
    api.put(limit_url(registered_user_id), json={'search_daily_limit': 1}, headers=headers)

    response = api.put(
        limit_url(registered_user_id), json={'search_daily_limit': None}, headers=headers
    )

    assert response.json() == {
        'user_id': registered_user_id,
        'search_daily_limit': None,
        'effective_limit': 7,
    }


def test_limit_of_zero_blocks_all_searches(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    admin_token: str,
    source: FakeSearchSource,
) -> None:
    api.put(
        limit_url(registered_user_id),
        json={'search_daily_limit': 0},
        headers=auth_header(admin_token),
    )

    assert search(api, access_token) == status.HTTP_429_TOO_MANY_REQUESTS
    assert source.queries == []


@pytest.mark.parametrize('limit', [-1, 1001, 'many'])
def test_invalid_limit_returns_422(
    api: TestClient, registered_user_id: int, admin_token: str, limit: object
) -> None:
    response = api.put(
        limit_url(registered_user_id),
        json={'search_daily_limit': limit},
        headers=auth_header(admin_token),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_unknown_user_returns_404(api: TestClient, admin_token: str) -> None:
    response = api.put(
        limit_url(999_999), json={'search_daily_limit': 5}, headers=auth_header(admin_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_normal_user_cannot_change_limits(
    api: TestClient, access_token: str, registered_user_id: int
) -> None:
    response = api.put(
        limit_url(registered_user_id),
        json={'search_daily_limit': 100},
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
