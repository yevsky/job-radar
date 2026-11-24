"""The CV's career snapshot: made on upload by a second AI call, and again on request."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.models import Resume
from tests.conftest import UseProvider, register_and_login
from tests.helpers import auth_header
from tests.resumes.conftest import CV_TEXT, EXTRACTED, INSIGHTS, CvProvider, answer, upload


def insights_url(resume_id: int) -> str:
    return f'/resumes/{resume_id}/insights'


def test_upload_stores_the_snapshot_next_to_what_the_ai_read(
    api: TestClient, access_token: str, provider: CvProvider, db: Session
) -> None:
    response = upload(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['extracted'] == EXTRACTED
    assert body['insights'] == INSIGHTS
    assert body['insights_with'] == 'fake/fake'
    resume = db.get(Resume, body['id'])
    assert resume is not None
    assert resume.insights == INSIGHTS
    assert len(provider.extract_calls()) == 1
    assert len(provider.insights_calls()) == 1


def test_the_snapshot_is_made_after_the_extraction(
    api: TestClient, access_token: str, provider: CvProvider
) -> None:
    upload(api, access_token)

    first, second = provider.calls
    assert provider.insights_calls() == [second]
    assert provider.extract_calls() == [first]


def test_the_snapshot_gets_the_level_code_counted_as_facts(
    api: TestClient, access_token: str, provider: CvProvider
) -> None:
    upload(api, access_token)

    [messages] = provider.insights_calls()
    user_text = messages[1].content
    assert 'Experience level: junior' in user_text
    assert 'Years of work in IT: 2' in user_text
    assert user_text.endswith(f'<resume>\n{CV_TEXT}\n</resume>')


def test_without_extracted_data_the_facts_say_unknown(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    # The extraction answers no JSON twice (it fails); the snapshot still works
    fake = CvProvider(responses=['no json here'])
    use_provider(fake)

    body = upload(api, access_token).json()

    assert body['extracted'] is None
    assert body['insights'] == INSIGHTS
    [messages] = fake.insights_calls()
    assert 'Experience level: unknown' in messages[1].content
    assert 'Years of work in IT: unknown' in messages[1].content


def test_a_failed_snapshot_still_stores_the_cv(
    api: TestClient, access_token: str, use_provider: UseProvider, db: Session
) -> None:
    use_provider(CvProvider(responses=[answer()], insights='not json'))

    response = upload(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['extracted'] == EXTRACTED
    assert body['insights'] is None
    assert body['insights_with'] is None
    assert db.get(Resume, body['id']) is not None


def test_the_snapshot_is_lenient_with_long_lists_and_text(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    noisy = {
        'summary': '  ' + 'x' * 900,
        'industries': ['A', 'a', '', 'B', 'C', 'D', 'E', 'F'],
        'roles': ['Junior Backend Developer', 42, '  '],
        'unknown_field': 'ignored',
    }
    use_provider(CvProvider(responses=[answer()], insights=answer(noisy)))

    insights = upload(api, access_token).json()['insights']

    assert len(insights['summary']) == 800
    assert insights['industries'] == ['A', 'B', 'C', 'D', 'E']
    assert insights['roles'] == ['Junior Backend Developer']
    assert insights['expertise'] == []
    assert insights['advice'] is None


# --- making it again ---------------------------------------------------------------------


@pytest.fixture
def resume_id(api: TestClient, access_token: str, use_provider: UseProvider) -> int:
    """A CV whose snapshot failed on upload."""
    use_provider(CvProvider(responses=[answer()], insights='not json'))
    return int(upload(api, access_token).json()['id'])


def test_insights_again_stores_the_snapshot(
    api: TestClient, access_token: str, resume_id: int, use_provider: UseProvider
) -> None:
    fake = CvProvider(responses=[answer()])
    use_provider(fake)

    response = api.post(insights_url(resume_id), headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['insights'] == INSIGHTS
    assert response.json()['extracted'] == EXTRACTED  # unchanged, not read again
    assert fake.extract_calls() == []
    assert len(fake.insights_calls()) == 1


def test_insights_again_replaces_the_old_snapshot(
    api: TestClient, access_token: str, provider: CvProvider, use_provider: UseProvider
) -> None:
    del provider
    resume = upload(api, access_token).json()
    use_provider(CvProvider(insights=answer({**INSIGHTS, 'roles': ['Python Developer']})))

    response = api.post(insights_url(resume['id']), headers=auth_header(access_token))

    assert response.json()['insights']['roles'] == ['Python Developer']


def test_insights_again_with_the_ai_down_returns_502(
    api: TestClient, access_token: str, resume_id: int, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(fail=True))

    response = api.post(insights_url(resume_id), headers=auth_header(access_token))

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


def test_insights_for_another_users_cv_returns_404(
    api: TestClient, resume_id: int, use_provider: UseProvider
) -> None:
    fake = CvProvider()
    use_provider(fake)
    _, other_token = register_and_login(api, 'other@example.com')

    response = api.post(insights_url(resume_id), headers=auth_header(other_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert fake.calls == []


def test_insights_without_token_returns_401(api: TestClient) -> None:
    response = api.post(insights_url(1))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_the_list_shows_the_snapshot(
    api: TestClient, access_token: str, provider: CvProvider
) -> None:
    del provider
    upload(api, access_token)

    [listed] = api.get('/resumes', headers=auth_header(access_token)).json()

    assert listed['insights'] == INSIGHTS
