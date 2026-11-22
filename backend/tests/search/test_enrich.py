"""Saving a search result fills its empty fields from the full page (issue #80)."""

import json
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.core.config import settings
from app.models import JobOffer
from app.search_sources.page_reader import FakePageReader
from tests.conftest import UsePages, UseProvider
from tests.helpers import auth_header

URL = '/search/results'
LINK = 'https://justjoin.it/job-offer/codesky-python-developer-wroclaw'
PAGE_TEXT = (
    'Junior Python Developer at Codesky, Wrocław. B2B. Python, FastAPI. Apply by 2026-12-15.'
)
ANSWER = {
    'title': 'Junior Python Developer',
    'company_name': 'Codesky',
    'location': 'Wrocław',
    'experience_level': 'junior',
    'employment_type': 'b2b',
    'deadline': '2026-12-15',
    'technologies': ['Python', 'FastAPI'],
}


def thin_result(**overrides: Any) -> dict[str, Any]:
    """What Tavily usually gives: a title, a company guessed from the link, the link."""
    body: dict[str, Any] = {
        'title': 'Python Developer',
        'company_name': 'Codesky',
        'url': LINK,
        'found_via': 'tavily',
    }
    body.update(overrides)
    return body


def save(api: TestClient, token: str, **overrides: Any) -> Any:
    return api.post(URL, json=thin_result(**overrides), headers=auth_header(token))


@pytest.fixture
def provider(use_provider: UseProvider) -> FakeAIProvider:
    """The AI answers ANSWER to every call."""
    fake = FakeAIProvider(responses=[json.dumps(ANSWER, ensure_ascii=False)])
    use_provider(fake)
    return fake


@pytest.fixture
def pages(use_pages: UsePages) -> FakePageReader:
    """The offer's page can be read and has PAGE_TEXT."""
    reader = FakePageReader({LINK: PAGE_TEXT})
    use_pages(reader)
    return reader


def test_empty_fields_are_filled_from_the_page(
    api: TestClient, access_token: str, provider: FakeAIProvider, pages: FakePageReader
) -> None:
    response = save(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['enriched'] is True
    assert body['location'] == 'Wrocław'
    assert body['experience_level'] == 'junior'
    assert body['employment_type'] == 'b2b'
    assert body['deadline'].startswith('2026-12-15')
    assert body['technologies'] == ['FastAPI', 'Python']
    assert body['description'] == PAGE_TEXT
    assert pages.urls == [LINK]
    assert PAGE_TEXT in provider.calls[0][1].content


def test_filled_fields_are_stored(
    api: TestClient, access_token: str, provider: FakeAIProvider, pages: FakePageReader
) -> None:
    del provider, pages
    offer_id = save(api, access_token).json()['id']

    details = api.get(f'/job-offers/{offer_id}', headers=auth_header(access_token)).json()
    assert details['location'] == 'Wrocław'
    assert details['technologies'] == ['FastAPI', 'Python']


def test_what_the_source_gave_is_never_overwritten(
    api: TestClient, access_token: str, provider: FakeAIProvider, pages: FakePageReader
) -> None:
    del provider, pages
    response = save(
        api,
        access_token,
        location='Remote',
        experience_level='middle',
        employment_type='full_time',
        technologies=['Django'],
        description='Snippet from the search.',
    )

    body = response.json()
    assert body['enriched'] is True
    assert body['location'] == 'Remote'
    assert body['experience_level'] == 'middle'
    assert body['employment_type'] == 'full_time'
    assert body['technologies'] == ['Django']
    assert body['description'] == 'Snippet from the search.'
    assert body['title'] == 'Python Developer'  # the model's 'Junior Python Developer' isn't used
    assert body['deadline'].startswith('2026-12-15')  # the source gave none, so it's filled


def test_without_a_page_the_results_description_is_parsed(
    api: TestClient, access_token: str, provider: FakeAIProvider, use_pages: UsePages
) -> None:
    use_pages(FakePageReader())  # the page can't be read
    response = save(api, access_token, description='Python, FastAPI, Wrocław, junior.')

    body = response.json()
    assert body['enriched'] is True
    assert body['location'] == 'Wrocław'
    assert body['description'] == 'Python, FastAPI, Wrocław, junior.'
    assert 'Python, FastAPI, Wrocław, junior.' in provider.calls[0][1].content


def test_without_a_tavily_key_the_description_is_parsed(
    api: TestClient, access_token: str, provider: FakeAIProvider, use_pages: UsePages
) -> None:
    del provider
    use_pages(None)

    response = save(api, access_token, description='Python, FastAPI, Wrocław, junior.')

    assert response.json()['enriched'] is True


def test_without_page_or_description_the_ai_is_not_called(
    api: TestClient, access_token: str, provider: FakeAIProvider, use_pages: UsePages
) -> None:
    use_pages(FakePageReader())

    response = save(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['enriched'] is False
    assert provider.calls == []


def test_ai_down_still_saves_the_offer(
    api: TestClient,
    access_token: str,
    use_provider: UseProvider,
    pages: FakePageReader,
    db: Session,
) -> None:
    del pages
    use_provider(FakeAIProvider(fail=True))

    response = save(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['enriched'] is False
    assert body['location'] is None
    assert db.get(JobOffer, body['id']) is not None


def test_bad_ai_answers_still_save_the_offer(
    api: TestClient, access_token: str, use_provider: UseProvider, pages: FakePageReader
) -> None:
    del pages
    use_provider(FakeAIProvider(responses=['no json here']))

    response = save(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['enriched'] is False


def test_saving_the_same_link_again_does_not_call_the_ai(
    api: TestClient, access_token: str, provider: FakeAIProvider, pages: FakePageReader
) -> None:
    first = save(api, access_token)
    second = save(api, access_token)

    assert second.status_code == status.HTTP_200_OK
    assert second.json()['id'] == first.json()['id']
    assert second.json()['enriched'] is False
    assert second.json()['location'] == 'Wrocław'  # filled the first time
    assert len(provider.calls) == 1
    assert pages.urls == [LINK]


def test_enrichment_can_be_switched_off(
    api: TestClient,
    access_token: str,
    provider: FakeAIProvider,
    pages: FakePageReader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, 'ai_enrich_saved_results', False)

    response = save(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['enriched'] is False
    assert provider.calls == []
    assert pages.urls == []
