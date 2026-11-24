"""POST/GET /job-offers/{id}/summary: the AI summary of a posting, one per offer."""

import json
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.ai.prompts import OFFER_SUMMARY_VERSION
from app.models import JobOffer
from app.models.enums import SourceKind
from tests.conftest import UseProvider, register_and_login
from tests.helpers import auth_header, make_offer

DESCRIPTION = (
    'Codesky builds booking APIs for hotels. You will write FastAPI services and tests. '
    'Required: 1+ year of Python, PostgreSQL. Nice to have: Docker. We offer 12-16k PLN '
    'net/month on B2B, hybrid work in Wrocław and a training budget.'
)
SUMMARY: dict[str, Any] = {
    'overview': 'Codesky builds booking APIs for hotels and looks for a junior Python developer.',
    'responsibilities': ['Write FastAPI services', 'Write tests'],
    'must_have': ['1+ year of Python', 'PostgreSQL'],
    'nice_to_have': ['Docker'],
    'benefits': ['Training budget'],
    'salary': '12-16k PLN net/month, B2B',
    'work_mode': 'hybrid',
    'missing_info': [],
}


def answer(**overrides: Any) -> str:
    return json.dumps({**SUMMARY, **overrides})


def url(offer_id: int) -> str:
    return f'/job-offers/{offer_id}/summary'


@pytest.fixture
def provider(use_provider: UseProvider) -> FakeAIProvider:
    fake = FakeAIProvider(responses=[answer()])
    use_provider(fake)
    return fake


@pytest.fixture
def offer(db: Session) -> JobOffer:
    """A public offer with a description."""
    public = make_offer(source=SourceKind.POSTED, description=DESCRIPTION)
    db.add(public)
    db.flush()
    return public


def run(api: TestClient, token: str, offer_id: int) -> Any:
    return api.post(url(offer_id), headers=auth_header(token))


# --- making a summary ---------------------------------------------------------------------


def test_summary_without_token_returns_401(api: TestClient, offer: JobOffer) -> None:
    assert api.post(url(offer.id)).status_code == status.HTTP_401_UNAUTHORIZED
    assert api.get(url(offer.id)).status_code == status.HTTP_401_UNAUTHORIZED


def test_summary_is_stored_on_the_offer_and_returned(
    api: TestClient, access_token: str, offer: JobOffer, provider: FakeAIProvider, db: Session
) -> None:
    response = run(api, access_token, offer.id)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert {k: body[k] for k in SUMMARY} == SUMMARY
    assert body['job_offer_id'] == offer.id
    assert body['summary_with'] == 'fake/fake'
    assert body['prompt_version'] == OFFER_SUMMARY_VERSION
    assert body['created_at']
    db.refresh(offer)
    assert offer.summary == SUMMARY
    assert offer.summary_with == 'fake/fake'
    assert offer.summary_prompt_version == OFFER_SUMMARY_VERSION
    assert offer.summarized_at is not None
    assert len(provider.calls) == 1


def test_the_ai_gets_the_posting_inside_the_untrusted_block(
    api: TestClient, access_token: str, offer: JobOffer, provider: FakeAIProvider
) -> None:
    run(api, access_token, offer.id)

    [messages] = provider.calls
    user_text = messages[1].content
    assert user_text.startswith('<job_posting>\nTitle: Backend Developer')
    assert DESCRIPTION in user_text
    assert user_text.endswith('</job_posting>')
    assert 'untrusted' in messages[0].content


def test_get_returns_the_stored_summary(
    api: TestClient, access_token: str, offer: JobOffer, provider: FakeAIProvider
) -> None:
    created = run(api, access_token, offer.id).json()

    response = api.get(url(offer.id), headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == created
    assert len(provider.calls) == 1  # reading costs no AI call


def test_get_before_any_summary_returns_404(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    response = api.get(url(offer.id), headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'No summary yet'


def test_running_again_replaces_the_summary(
    api: TestClient, access_token: str, offer: JobOffer, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(responses=[answer()]))
    run(api, access_token, offer.id)
    use_provider(FakeAIProvider(responses=[answer(overview='A newer summary.')]))

    run(api, access_token, offer.id)

    body = api.get(url(offer.id), headers=auth_header(access_token)).json()
    assert body['overview'] == 'A newer summary.'


def test_one_summary_is_shared_by_every_user_who_sees_the_offer(
    api: TestClient, access_token: str, offer: JobOffer, provider: FakeAIProvider
) -> None:
    del provider
    run(api, access_token, offer.id)
    _, other_token = register_and_login(api, 'other@example.com')

    response = api.get(url(offer.id), headers=auth_header(other_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['overview'] == SUMMARY['overview']


def test_a_lenient_answer_is_cleaned(
    api: TestClient, access_token: str, offer: JobOffer, use_provider: UseProvider
) -> None:
    noisy = answer(
        salary='not given',
        work_mode='On-site',
        must_have=['Python', 'python', '', 'x' * 300],
        benefits=[f'Benefit {n}' for n in range(12)],
        extra='ignored',
    )
    use_provider(FakeAIProvider(responses=[noisy]))

    body = run(api, access_token, offer.id).json()

    assert body['salary'] is None
    assert body['work_mode'] == 'onsite'
    assert body['must_have'] == ['Python', 'x' * 120]
    assert len(body['benefits']) == 8
    assert 'extra' not in body


def test_an_unknown_work_mode_becomes_null(
    api: TestClient, access_token: str, offer: JobOffer, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(responses=[answer(work_mode='sometimes')]))

    assert run(api, access_token, offer.id).json()['work_mode'] is None


# --- refusals -------------------------------------------------------------------------------


def test_offer_without_description_returns_422_and_asks_no_ai(
    api: TestClient, access_token: str, db: Session, provider: FakeAIProvider
) -> None:
    bare = make_offer('https://example.com/jobs/bare', source=SourceKind.POSTED)
    short = make_offer(
        'https://example.com/jobs/short', source=SourceKind.POSTED, description='Python dev.'
    )
    db.add_all([bare, short])
    db.flush()

    for offer in (bare, short):
        response = run(api, access_token, offer.id)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert 'no description' in response.json()['detail']
    assert provider.calls == []


def test_unknown_offer_returns_404(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    assert run(api, access_token, 999_999).status_code == status.HTTP_404_NOT_FOUND
    response = api.get(url(999_999), headers=auth_header(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'Job offer not found'


def test_another_users_private_offer_returns_404(
    api: TestClient, access_token: str, db: Session, provider: FakeAIProvider
) -> None:
    other_id, _ = register_and_login(api, 'other@example.com')
    private = make_offer(
        'https://example.com/jobs/private',
        source=SourceKind.MANUAL,
        owner_id=other_id,
        description=DESCRIPTION,
    )
    db.add(private)
    db.flush()

    assert run(api, access_token, private.id).status_code == status.HTTP_404_NOT_FOUND
    response = api.get(url(private.id), headers=auth_header(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert provider.calls == []


def test_own_private_offer_can_be_summarised(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    db: Session,
    provider: FakeAIProvider,
) -> None:
    del provider
    mine = make_offer(
        'https://example.com/jobs/mine',
        source=SourceKind.MANUAL,
        owner_id=registered_user_id,
        description=DESCRIPTION,
    )
    db.add(mine)
    db.flush()

    assert run(api, access_token, mine.id).status_code == status.HTTP_201_CREATED


def test_ai_down_returns_502_and_keeps_the_old_summary(
    api: TestClient, access_token: str, offer: JobOffer, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(responses=[answer()]))
    run(api, access_token, offer.id)
    use_provider(FakeAIProvider(fail=True))

    response = run(api, access_token, offer.id)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    body = api.get(url(offer.id), headers=auth_header(access_token)).json()
    assert body['overview'] == SUMMARY['overview']


def test_an_answer_without_overview_twice_returns_502(
    api: TestClient, access_token: str, offer: JobOffer, use_provider: UseProvider
) -> None:
    fake = FakeAIProvider(responses=[answer(overview='')])
    use_provider(fake)

    response = run(api, access_token, offer.id)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert len(fake.calls) == 2  # one retry with the errors
    response = api.get(url(offer.id), headers=auth_header(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND
