import json
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.models import JobOffer
from tests.conftest import UseProvider
from tests.helpers import auth_header

URL = '/job-offers/parse'
POSTING = (
    'Junior Python Developer - Codesky (Wrocław, hybrid). B2B, 9 000 - 12 000 PLN net. '
    'Python, FastAPI, PostgreSQL, Docker. Nice to have: React. Apply by 15 December 2026.'
)
ANSWER = {
    'title': 'Junior Python Developer',
    'company_name': 'Codesky',
    'location': 'Wrocław',
    'experience_level': 'junior',
    'employment_type': 'b2b',
    'deadline': '2026-12-15',
    'technologies': ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'React'],
}


def fake(*answers: dict[str, Any] | str) -> FakeAIProvider:
    return FakeAIProvider(
        responses=[a if isinstance(a, str) else json.dumps(a, ensure_ascii=False) for a in answers]
    )


def parse(api: TestClient, token: str, **body: Any) -> Any:
    return api.post(URL, json={'text': POSTING, **body}, headers=auth_header(token))


def count_offers(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(JobOffer)) or 0


def test_parse_without_token_returns_401(api: TestClient) -> None:
    assert api.post(URL, json={'text': POSTING}).status_code == status.HTTP_401_UNAUTHORIZED


def test_posting_is_parsed_into_a_draft_and_nothing_is_saved(
    api: TestClient, access_token: str, use_provider: UseProvider, db: Session
) -> None:
    use_provider(fake(ANSWER))

    response = parse(api, access_token, url='https://justjoin.it/job-offer/codesky-python')

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        **ANSWER,
        'url': 'https://justjoin.it/job-offer/codesky-python',
        'description': POSTING,
        'parsed_with': 'fake/fake',
    }
    assert count_offers(db) == 0


def test_link_is_optional(api: TestClient, access_token: str, use_provider: UseProvider) -> None:
    use_provider(fake(ANSWER))

    assert parse(api, access_token).json()['url'] is None


def test_a_link_in_the_posting_fills_the_url(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(fake(ANSWER))
    text = f'{POSTING}\nApply here: https://codesky.pl/careers/junior-python.'

    response = parse(api, access_token, text=text)

    body = response.json()
    assert body['url'] == 'https://codesky.pl/careers/junior-python'
    assert body['description'] == text


def test_the_given_link_wins_over_one_in_the_posting(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(fake(ANSWER))

    response = parse(
        api,
        access_token,
        text=f'{POSTING} More: https://codesky.pl/about',
        url='https://justjoin.it/job-offer/codesky-python',
    )

    assert response.json()['url'] == 'https://justjoin.it/job-offer/codesky-python'


def test_the_model_gets_the_posting_inside_the_untrusted_block(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    provider = fake(ANSWER)
    use_provider(provider)

    parse(api, access_token)

    [messages] = provider.calls
    assert messages[1].content == f'<job_posting>\n{POSTING}\n</job_posting>'


def test_unknown_values_from_the_model_become_null(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(
        fake(
            {
                **ANSWER,
                'experience_level': 'expert',
                'employment_type': 'freelance',
                'deadline': 'ASAP',
            }
        )
    )

    response = parse(api, access_token)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert (body['experience_level'], body['employment_type'], body['deadline']) == (None,) * 3
    assert body['title'] == 'Junior Python Developer'


def test_a_bad_first_answer_is_retried(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    provider = fake({'company_name': 'Codesky'}, ANSWER)  # first one has no title
    use_provider(provider)

    response = parse(api, access_token)

    assert response.status_code == status.HTTP_200_OK
    assert len(provider.calls) == 2


def test_two_bad_answers_return_502(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(fake('Sorry, I cannot help with that.'))

    response = parse(api, access_token)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert "didn't answer" in response.json()['detail']


def test_provider_down_returns_502(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(fail=True))

    response = parse(api, access_token)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.parametrize(
    'body',
    [
        {'text': ''},
        {'text': ' ' * 100},  # only spaces: empty after trimming
        {'text': 'Python dev'},  # too short to be a posting
        {'text': 'x' * 20_001},
        {'text': POSTING, 'url': 'not a link'},
        {},
    ],
    ids=['empty', 'spaces', 'short', 'long', 'bad-url', 'missing'],
)
def test_bad_request_returns_422_and_calls_no_ai(
    api: TestClient, access_token: str, use_provider: UseProvider, body: dict[str, Any]
) -> None:
    provider = fake(ANSWER)
    use_provider(provider)

    response = api.post(URL, json=body, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert provider.calls == []


def test_draft_can_be_saved_as_it_is_once_the_company_is_known(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(fake(ANSWER))
    draft = parse(api, access_token, url='https://justjoin.it/job-offer/codesky-python').json()

    fields = {key: value for key, value in draft.items() if key != 'parsed_with'}
    response = api.post('/job-offers', json=fields, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_201_CREATED
    saved = response.json()
    assert saved['deadline'].startswith('2026-12-15')
    assert saved['is_private'] is True
    assert saved['employment_type'] == 'b2b'
