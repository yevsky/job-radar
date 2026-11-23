"""add_offer_from_text: a posting pasted in the chat becomes a private offer after confirming."""

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import ToolTurn
from app.ai.fake import FakeAIProvider
from app.models import ChatAction, JobOffer
from app.services.chat import OLD_MESSAGE_CHARS
from tests.chat.conftest import Headers, call, say, send
from tests.conftest import UseProvider

POSTING = (
    'Junior Python Developer at Acme. We build payment APIs in Wrocław. You will work with '
    'Python, FastAPI and PostgreSQL in a small team. Full time, hybrid. Requirements: one year '
    'of Python, SQL basics, English B2. Apply: https://acme.example.com/jobs/42.'
)
PARSED = {
    'title': 'Junior Python Developer',
    'company_name': 'Acme',
    'location': 'Wrocław',
    'experience_level': 'junior',
    'employment_type': 'full_time',
    'deadline': None,
    'technologies': ['Python', 'FastAPI', 'PostgreSQL'],
}


def use(use_provider: UseProvider, *turns: ToolTurn, **parsed: Any) -> FakeAIProvider:
    """The model plays the turns; reading the posting answers PARSED (with changes)."""
    fake = FakeAIProvider(responses=[json.dumps({**PARSED, **parsed})], turns=list(turns))
    use_provider(fake)
    return fake


def confirm(api: TestClient, headers: Headers, chat_id: int, action_id: int) -> Any:
    return api.post(f'/chat/{chat_id}/actions/{action_id}/confirm', headers=headers).json()


def test_a_pasted_posting_waits_for_the_user(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider, db: Session
) -> None:
    use(use_provider, call('add_offer_from_text'))
    body = send(api, headers, chat_id, f'Add this offer please:\n{POSTING}')

    action = body['pending_actions'][0]
    assert action['tool'] == 'add_offer_from_text'
    assert action['summary'] == (
        'Add "Junior Python Developer" at Acme (Wrocław; junior; full_time; '
        'Python, FastAPI, PostgreSQL) to My offers'
    )
    assert db.scalar(select(JobOffer)) is None  # nothing saved before confirming


def test_confirming_adds_a_private_offer(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider, db: Session
) -> None:
    fake = use(use_provider, call('add_offer_from_text'))
    action = send(api, headers, chat_id, POSTING)['pending_actions'][0]
    reads = len(fake.calls)

    body = confirm(api, headers, chat_id, action['id'])
    assert body['message']['content'] == (
        'Done: Added "Junior Python Developer" at Acme to My offers.'
    )
    assert len(fake.calls) == reads  # the posting is read once, before confirming
    offer = db.scalar(select(JobOffer))
    assert offer is not None
    assert offer.url == 'https://acme.example.com/jobs/42'
    assert offer.description == POSTING
    assert offer.owner_id is not None
    assert offer.source == 'manual'
    assert sorted(t.name for t in offer.technologies) == ['FastAPI', 'PostgreSQL', 'Python']
    listed = api.get('/job-offers/mine', headers=headers).json()
    assert [o['title'] for o in listed] == ['Junior Python Developer']


def test_the_model_cannot_fill_the_offer_itself(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    fake_draft = {'title': 'CEO', 'company_name': 'Evil', 'url': 'https://evil.example.com'}
    use(use_provider, call('add_offer_from_text', draft=fake_draft))
    action = send(api, headers, chat_id, POSTING)['pending_actions'][0]
    assert action['summary'].startswith('Add "Junior Python Developer" at Acme')


def test_without_a_link_the_model_asks_for_it(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider, db: Session
) -> None:
    posting = POSTING.split(' Apply:')[0]
    fake = use(use_provider, call('add_offer_from_text'), say('What is the link?'))
    body = send(api, headers, chat_id, posting)
    assert body['pending_actions'] == []
    result = fake.tool_calls[1][-1]
    assert 'no link' in result.content  # type: ignore[union-attr]

    # the link in the next message; the posting is still read from the earlier one
    use(use_provider, call('add_offer_from_text', url='https://acme.example.com/jobs/7'))
    action = send(api, headers, chat_id, 'https://acme.example.com/jobs/7')['pending_actions'][0]
    confirm(api, headers, chat_id, action['id'])
    offer = db.scalar(select(JobOffer))
    assert offer is not None
    assert offer.url == 'https://acme.example.com/jobs/7'
    assert offer.description == posting


def test_a_missing_company_is_asked_for(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    fake = use(use_provider, call('add_offer_from_text'), say('Which company?'), company_name=None)
    assert send(api, headers, chat_id, POSTING)['pending_actions'] == []
    assert "doesn't name the company" in fake.tool_calls[1][-1].content  # type: ignore[union-attr]

    use(use_provider, call('add_offer_from_text', company_name='Acme Labs'), company_name=None)
    action = send(api, headers, chat_id, 'It is Acme Labs')['pending_actions'][0]
    assert ' at Acme Labs ' in action['summary']


def test_no_posting_in_the_chat(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    fake = use(use_provider, call('add_offer_from_text'), say('Please paste it.'))
    assert send(api, headers, chat_id, 'Add an offer')['pending_actions'] == []
    assert 'paste the whole posting' in fake.tool_calls[1][-1].content  # type: ignore[union-attr]
    assert fake.calls == []  # nothing to read, so the AI wasn't asked


def test_a_known_link_is_refused(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    fake = use(use_provider, call('add_offer_from_text'))
    action = send(api, headers, chat_id, POSTING)['pending_actions'][0]
    confirm(api, headers, chat_id, action['id'])

    fake.turns = [call('add_offer_from_text'), say('You have it already.')]
    fake.tool_calls.clear()
    assert send(api, headers, chat_id, POSTING)['pending_actions'] == []
    assert 'already in the app' in fake.tool_calls[1][-1].content  # type: ignore[union-attr]


def test_a_reading_failure_goes_back_to_the_model(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider, db: Session
) -> None:
    fake = FakeAIProvider(responses=['not json'], turns=[call('add_offer_from_text'), say('Sorry')])
    use_provider(fake)
    assert send(api, headers, chat_id, POSTING)['pending_actions'] == []
    assert "Couldn't read the posting" in fake.tool_calls[1][-1].content  # type: ignore[union-attr]
    assert db.scalar(select(ChatAction)) is None


def test_an_older_long_message_is_cut_in_the_history(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    long_text = 'x' * (OLD_MESSAGE_CHARS + 500)
    fake = use(use_provider, say('Ok'))
    send(api, headers, chat_id, long_text)
    assert fake.tool_calls[0][-1].content == long_text  # type: ignore[union-attr]
    send(api, headers, chat_id, 'And now?')
    history = fake.tool_calls[1]
    old = [m for m in history if getattr(m, 'content', '').startswith('xxx')]
    assert len(old[0].content) < len(long_text)  # type: ignore[union-attr]
    assert history[-1].content == 'And now?'  # type: ignore[union-attr]
