"""POST /search/analysis: match a search result without storing anything."""

from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.ai.prompts import OFFER_ANALYSIS_VERSION
from app.models import AiAnalysis, JobOffer
from tests.analyses.conftest import ANSWER, SCORE, add_resume
from tests.conftest import UseProvider
from tests.helpers import auth_header

URL = '/search/analysis'

RESULT: dict[str, Any] = {
    'title': 'Junior Python Developer',
    'company_name': 'Codesky',
    'url': 'https://example.com/jobs/found',
    'location': 'Wroclaw',
    'experience_level': 'junior',
    'employment_type': 'b2b',
    'description': 'Required: Python, FastAPI, PostgreSQL. Nice to have: Docker.',
    'found_via': 'tavily',
}


def analyse(api: TestClient, token: str, resume_id: int | None = None, **result: Any) -> Any:
    body = {'result': {**RESULT, **result}, 'resume_id': resume_id}
    return api.post(URL, json=body, headers=auth_header(token))


def count(db: Session, model: type[AiAnalysis] | type[JobOffer]) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_without_token_returns_401(api: TestClient) -> None:
    response = api.post(URL, json={'result': RESULT})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_returns_the_analysis_and_stores_nothing(
    api: TestClient, token: str, provider: FakeAIProvider, db: Session
) -> None:
    response = analyse(api, token)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['score'] == SCORE
    assert body['matched_skills'] == ['Python', 'FastAPI']
    assert body['missing_skills'] == ['PostgreSQL']
    assert body['summary'] == ANSWER['summary']
    assert body['prompt_version'] == OFFER_ANALYSIS_VERSION
    assert 'id' not in body
    assert 'created_at' not in body
    assert count(db, AiAnalysis) == 0
    assert count(db, JobOffer) == 0  # the result isn't saved as an offer either
    assert 'Required: Python, FastAPI, PostgreSQL' in provider.calls[0][1].content


def test_the_result_must_be_a_valid_search_result(
    api: TestClient, token: str, provider: FakeAIProvider
) -> None:
    body = {'result': {**RESULT, 'url': 'not a link'}}
    response = api.post(URL, json=body, headers=auth_header(token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert provider.calls == []


def test_a_cv_goes_to_the_model(
    api: TestClient,
    token: str,
    registered_user_id: int,
    provider: FakeAIProvider,
    db: Session,
) -> None:
    resume = add_resume(db, registered_user_id)

    response = analyse(api, token, resume.id)

    assert response.status_code == status.HTTP_200_OK
    assert '<resume>\nBuilt 3 FastAPI services\n</resume>' in provider.calls[0][1].content


def test_another_users_cv_returns_404(
    api: TestClient,
    token: str,
    other: tuple[int, str],
    provider: FakeAIProvider,
    db: Session,
) -> None:
    other_id, _ = other
    resume = add_resume(db, other_id)

    response = analyse(api, token, resume.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'CV not found'
    assert provider.calls == []


def test_an_empty_profile_returns_422(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    response = analyse(api, access_token)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()['detail'] == 'Fill your profile first: add a desired position or a skill'
    assert provider.calls == []


def test_provider_down_returns_502(api: TestClient, token: str, use_provider: UseProvider) -> None:
    use_provider(FakeAIProvider(fail=True))
    assert analyse(api, token).status_code == status.HTTP_502_BAD_GATEWAY
