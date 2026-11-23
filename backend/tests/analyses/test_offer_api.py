"""POST/GET /job-offers/{id}/analysis: run a match, store it, read the newest one."""

from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.ai.prompts import OFFER_ANALYSIS_VERSION
from app.models import AiAnalysis, JobOffer, User
from app.models.enums import SourceKind
from tests.analyses.conftest import ANSWER, SCORE, add_resume, answer, offer_fields
from tests.conftest import UseProvider
from tests.helpers import auth_header, make_offer


def url(offer_id: int) -> str:
    return f'/job-offers/{offer_id}/analysis'


def run(api: TestClient, token: str, offer_id: int, resume_id: int | None = None) -> Any:
    return api.post(url(offer_id), json={'resume_id': resume_id}, headers=auth_header(token))


def count_analyses(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(AiAnalysis)) or 0


@pytest.fixture
def private_offer(db: Session, other: tuple[int, str]) -> JobOffer:
    """An offer only the other user can see."""
    other_id, _ = other
    offer = make_offer(
        'https://example.com/jobs/private', source=SourceKind.MANUAL, owner_id=other_id
    )
    db.add(offer)
    db.flush()
    return offer


# --- running an analysis ----------------------------------------------------------------


def test_run_without_token_returns_401(api: TestClient, offer: JobOffer) -> None:
    response = api.post(url(offer.id), json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_run_stores_the_analysis_and_returns_it(
    api: TestClient, token: str, offer: JobOffer, provider: FakeAIProvider, db: Session
) -> None:
    response = run(api, token, offer.id)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['job_offer_id'] == offer.id
    assert body['resume_id'] is None
    assert body['score'] == SCORE
    assert body['breakdown'] == {
        'required_skills': 30,
        'nice_to_have_skills': 0,
        'experience_level': 20,
        'location': 10,
        'employment_type': 5,
        'role_fit': 9,
    }
    assert body['summary'] == ANSWER['summary']
    assert body['reasons'] == ANSWER['reasons']
    assert body['red_flags'] == ['Unpaid 2-week trial']
    assert body['matched_skills'] == ['Python', 'FastAPI']
    assert body['missing_skills'] == ['PostgreSQL']
    assert (body['provider'], body['model']) == ('fake', 'fake')
    assert body['prompt_version'] == OFFER_ANALYSIS_VERSION
    assert body['created_at']

    row = db.get(AiAnalysis, body['id'])
    assert row is not None
    assert row.score == SCORE
    assert row.prompt_version == OFFER_ANALYSIS_VERSION
    assert len(provider.calls) == 2  # step 1 reads the requirements, step 2 judges


def test_an_empty_body_means_no_cv(
    api: TestClient, token: str, offer: JobOffer, provider: FakeAIProvider
) -> None:
    response = api.post(url(offer.id), json={}, headers=auth_header(token))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['resume_id'] is None
    assert '<resume>' not in provider.calls[1][1].content


def test_the_model_reads_the_offer_from_the_database(
    api: TestClient, token: str, db: Session, provider: FakeAIProvider
) -> None:
    offer = make_offer(source=SourceKind.POSTED, **offer_fields(description='Unique text 42'))
    db.add(offer)
    db.flush()

    run(api, token, offer.id)

    user_message = provider.calls[0][1].content
    assert 'Title: Junior Python Developer' in user_message
    assert 'Unique text 42' in user_message


def test_every_run_adds_a_row_and_get_returns_the_newest(
    api: TestClient, token: str, offer: JobOffer, use_provider: UseProvider, db: Session
) -> None:
    use_provider(FakeAIProvider(responses=[answer(summary='First'), answer(summary='Second')]))

    first = run(api, token, offer.id).json()
    second = run(api, token, offer.id).json()

    assert first['id'] != second['id']
    assert count_analyses(db) == 2
    response = api.get(url(offer.id), headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == second
    assert response.json()['summary'] == 'Second'


@pytest.mark.usefixtures('provider')
def test_own_private_offer_can_be_analysed(
    api: TestClient,
    other: tuple[int, str],
    private_offer: JobOffer,
) -> None:
    _, other_token = other
    response = run(api, other_token, private_offer.id)
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize(
    'profile',
    [
        {'desired_position': 'Python developer'},  # a position is enough
        {},  # skills only (set below)
    ],
)
@pytest.mark.usefixtures('provider')
def test_a_position_or_a_skill_is_enough(
    api: TestClient,
    access_token: str,
    offer: JobOffer,
    profile: dict[str, str],
) -> None:
    headers = auth_header(access_token)
    if profile:
        api.put('/profile/me', json=profile, headers=headers)
    else:
        api.put('/profile/me/skills', json={'skills': ['Python']}, headers=headers)

    assert run(api, access_token, offer.id).status_code == status.HTTP_201_CREATED


# --- with a CV ------------------------------------------------------------------------------


def test_run_with_a_cv_stores_it_and_shows_it_to_the_model(
    api: TestClient,
    token: str,
    registered_user_id: int,
    offer: JobOffer,
    provider: FakeAIProvider,
    db: Session,
) -> None:
    resume = add_resume(db, registered_user_id)

    response = run(api, token, offer.id, resume.id)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['resume_id'] == resume.id
    assert '<resume>\nBuilt 3 FastAPI services\n</resume>' in provider.calls[1][1].content


def test_another_users_cv_returns_404(
    api: TestClient,
    token: str,
    other: tuple[int, str],
    offer: JobOffer,
    provider: FakeAIProvider,
    db: Session,
) -> None:
    other_id, _ = other
    resume = add_resume(db, other_id)

    response = run(api, token, offer.id, resume.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'CV not found'
    assert provider.calls == []
    assert count_analyses(db) == 0


def test_an_unknown_cv_returns_404(
    api: TestClient, token: str, offer: JobOffer, provider: FakeAIProvider
) -> None:
    response = run(api, token, offer.id, 999_999)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert provider.calls == []


@pytest.mark.usefixtures('provider')
def test_deleting_the_cv_keeps_the_analysis_without_it(
    api: TestClient,
    token: str,
    registered_user_id: int,
    offer: JobOffer,
    db: Session,
) -> None:
    resume = add_resume(db, registered_user_id)
    run(api, token, offer.id, resume.id)

    deleted = api.delete(f'/resumes/{resume.id}', headers=auth_header(token))

    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    db.expire_all()  # the database set resume_id to NULL, not the session
    response = api.get(url(offer.id), headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['resume_id'] is None
    assert count_analyses(db) == 1


# --- offers the user can't see ------------------------------------------------------------


def test_another_users_private_offer_returns_404(
    api: TestClient, token: str, private_offer: JobOffer, provider: FakeAIProvider, db: Session
) -> None:
    response = run(api, token, private_offer.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'Job offer not found'
    assert provider.calls == []
    assert count_analyses(db) == 0


def test_get_of_another_users_private_offer_returns_404(
    api: TestClient, token: str, private_offer: JobOffer
) -> None:
    response = api.get(url(private_offer.id), headers=auth_header(token))
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'Job offer not found'


def test_an_unknown_offer_returns_404(
    api: TestClient, token: str, provider: FakeAIProvider
) -> None:
    assert run(api, token, 999_999).status_code == status.HTTP_404_NOT_FOUND
    assert provider.calls == []


# --- reading ---------------------------------------------------------------------------------


def test_get_before_any_run_returns_404(api: TestClient, token: str, offer: JobOffer) -> None:
    response = api.get(url(offer.id), headers=auth_header(token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'No analysis yet'


def test_each_user_only_sees_their_own_analyses(
    api: TestClient,
    token: str,
    other: tuple[int, str],
    offer: JobOffer,
    use_provider: UseProvider,
) -> None:
    _, other_token = other
    use_provider(
        FakeAIProvider(responses=[answer(summary='Mine')] * 2 + [answer(summary='Theirs')])
    )
    run(api, token, offer.id)

    assert api.get(url(offer.id), headers=auth_header(other_token)).status_code == 404

    run(api, other_token, offer.id)
    mine = api.get(url(offer.id), headers=auth_header(token)).json()
    theirs = api.get(url(offer.id), headers=auth_header(other_token)).json()
    assert (mine['summary'], theirs['summary']) == ('Mine', 'Theirs')


# --- errors ------------------------------------------------------------------------------------


def test_an_empty_profile_returns_422_before_calling_the_ai(
    api: TestClient, access_token: str, offer: JobOffer, provider: FakeAIProvider
) -> None:
    response = run(api, access_token, offer.id)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()['detail'] == 'Fill your profile first: add a desired position or a skill'
    assert provider.calls == []


def test_provider_down_returns_502_and_stores_nothing(
    api: TestClient, token: str, offer: JobOffer, use_provider: UseProvider, db: Session
) -> None:
    use_provider(FakeAIProvider(fail=True))

    response = run(api, token, offer.id)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert count_analyses(db) == 0


def test_two_bad_answers_return_502(
    api: TestClient, token: str, offer: JobOffer, use_provider: UseProvider, db: Session
) -> None:
    fake = FakeAIProvider(responses=[answer(role_fit=50)])
    use_provider(fake)

    response = run(api, token, offer.id)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert len(fake.calls) == 3  # step 1, then step 2 and its one retry
    assert count_analyses(db) == 0


# --- what deletes analyses ----------------------------------------------------------------------


@pytest.mark.usefixtures('provider')
def test_deleting_the_offer_deletes_its_analyses(
    api: TestClient,
    other: tuple[int, str],
    private_offer: JobOffer,
    db: Session,
) -> None:
    _, other_token = other
    run(api, other_token, private_offer.id)

    response = api.delete(f'/job-offers/{private_offer.id}', headers=auth_header(other_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert count_analyses(db) == 0


@pytest.mark.usefixtures('provider')
def test_deleting_the_user_deletes_their_analyses(
    api: TestClient,
    token: str,
    registered_user_id: int,
    offer: JobOffer,
    db: Session,
) -> None:
    run(api, token, offer.id)

    user = db.get(User, registered_user_id)
    assert user is not None
    db.delete(user)
    db.flush()

    assert count_analyses(db) == 0
