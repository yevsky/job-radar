import json
from typing import Any, override

import pytest
from fastapi.testclient import TestClient

from app.ai.base import ChatMessage
from app.ai.fake import FakeAIProvider
from tests.conftest import UseProvider
from tests.helpers import auth_header
from tests.resumes.pdf import make_pdf

CV_TEXT = (
    'Anna Kowalska\nJunior Python developer\nSkills: Python, FastAPI, Docker\nWroclaw or remote'
)
CV_PDF = make_pdf(CV_TEXT)
EXTRACTED = {
    'desired_position': 'Python developer',
    'experience_level': 'junior',
    'jobs': None,  # no dates: experience_years stays the model's
    'experience_years': 2.0,
    'skills': ['Python', 'FastAPI', 'Docker'],
    'locations': ['Wroclaw', 'Remote'],
    'employment_types': ['b2b', 'full_time'],
    'summary': 'Junior backend developer, 2 years with Python.',
}


INSIGHTS = {
    'summary': 'I am a junior Python developer who builds APIs with FastAPI and Docker.',
    'industries': ['Software engineering'],
    'expertise': ['REST API development', 'Containerised deployments (Docker)'],
    'roles': ['Junior Backend Developer', 'Python Developer'],
    'growth': ['Cloud platforms (AWS)'],
    'advice': 'Look for junior backend roles that use FastAPI.',
}


def answer(data: dict[str, Any] = EXTRACTED) -> str:
    return json.dumps(data, ensure_ascii=False)


def is_insights_call(messages: list[ChatMessage]) -> bool:
    return 'career snapshot' in messages[0].content


class CvProvider(FakeAIProvider):
    """Answers the career-snapshot prompt with `insights` and every other prompt (the
    extraction) like FakeAIProvider, so tests can count and check each kind of call."""

    def __init__(self, responses: list[str] | None = None, insights: str | None = None) -> None:
        super().__init__(responses=responses)
        self.insights = insights or answer(INSIGHTS)

    @override
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        if is_insights_call(messages):
            self.calls.append(list(messages))
            return self.insights
        return super().chat(messages, json_mode)

    def extract_calls(self) -> list[list[ChatMessage]]:
        return [m for m in self.calls if not is_insights_call(m)]

    def insights_calls(self) -> list[list[ChatMessage]]:
        return [m for m in self.calls if is_insights_call(m)]


def upload(
    api: TestClient,
    token: str,
    label: str = 'Backend CV',
    content: bytes = CV_PDF,
    file_name: str = 'anna-cv.pdf',
    content_type: str = 'application/pdf',
) -> Any:
    return api.post(
        '/resumes',
        files={'file': (file_name, content, content_type)},
        data={'label': label},
        headers=auth_header(token),
    )


@pytest.fixture
def provider(use_provider: UseProvider) -> CvProvider:
    """The AI reads every CV as EXTRACTED, and writes INSIGHTS as its snapshot."""
    fake = CvProvider(responses=[answer()])
    use_provider(fake)
    return fake
