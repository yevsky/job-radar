"""Shared data for the analysis API tests: a model answer, a filled profile, offers and a CV."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.models import JobOffer, Resume
from app.models.enums import EmploymentType, ExperienceLevel, SourceKind
from tests.conftest import UseProvider, register_and_login
from tests.helpers import auth_header, make_offer

ANSWER: dict[str, Any] = {
    'requirements': [
        {'text': 'Python', 'required': True, 'skill': 'Python'},
        {'text': 'FastAPI', 'required': True, 'skill': 'FastAPI'},
        {'text': 'PostgreSQL', 'required': True, 'skill': None},
        {'text': 'Docker', 'required': False, 'skill': None},
    ],
    'role_fit': 9,
    'summary': 'A junior Python role close to what you want; PostgreSQL is new to you.',
    'reasons': ['Python and FastAPI are your main skills'],
    'red_flags': ['Unpaid 2-week trial'],
}
# 2 of 3 required (30) + 0 of 1 nice (0) + same level (20) + Wroclaw (10) + B2B (5) + 9
SCORE = 30 + 0 + 20 + 10 + 5 + 9


def answer(**overrides: Any) -> str:
    return json.dumps({**ANSWER, **overrides})


@pytest.fixture
def provider(use_provider: UseProvider) -> FakeAIProvider:
    """The model answers ANSWER to every analysis."""
    fake = FakeAIProvider(responses=[answer()])
    use_provider(fake)
    return fake


def fill_profile(api: TestClient, token: str) -> None:
    headers = auth_header(token)
    profile = {'desired_position': 'Python developer', 'experience_level': 'junior'}
    api.put('/profile/me', json=profile, headers=headers)
    api.put('/profile/me/skills', json={'skills': ['Python', 'FastAPI']}, headers=headers)
    api.put('/profile/me/locations', json={'locations': ['Wrocław']}, headers=headers)
    api.put('/profile/me/employment-types', json={'employment_types': ['b2b']}, headers=headers)


@pytest.fixture
def token(api: TestClient, access_token: str) -> str:
    """A user with a filled profile: junior Python developer, Python + FastAPI, Wrocław, B2B."""
    fill_profile(api, access_token)
    return access_token


@pytest.fixture
def other(api: TestClient) -> tuple[int, str]:
    """A second user with a filled profile: (user id, token)."""
    user_id, other_token = register_and_login(api, 'other@example.com')
    fill_profile(api, other_token)
    return user_id, other_token


def offer_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        'title': 'Junior Python Developer',
        'location': 'Wroclaw',
        'experience_level': ExperienceLevel.JUNIOR,
        'employment_type': EmploymentType.B2B,
        'description': 'Required: Python, FastAPI, PostgreSQL. Nice to have: Docker.',
    }
    fields.update(overrides)
    return fields


@pytest.fixture
def offer(db: Session) -> JobOffer:
    """A public offer everyone can see."""
    public = make_offer(source=SourceKind.POSTED, **offer_fields())
    db.add(public)
    db.flush()
    return public


def add_resume(db: Session, user_id: int, label: str = 'Backend CV') -> Resume:
    resume = Resume(
        user_id=user_id, label=label, file_name='cv.pdf', text='Built 3 FastAPI services'
    )
    db.add(resume)
    db.flush()
    return resume
