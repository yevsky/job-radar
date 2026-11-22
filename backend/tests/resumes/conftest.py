import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

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
    'skills': ['Python', 'FastAPI', 'Docker'],
    'locations': ['Wroclaw', 'Remote'],
    'employment_types': ['b2b', 'full_time'],
    'summary': 'Junior backend developer, 2 years with Python.',
}


def answer(data: dict[str, Any] = EXTRACTED) -> str:
    return json.dumps(data, ensure_ascii=False)


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
def provider(use_provider: UseProvider) -> FakeAIProvider:
    """The AI reads every CV as EXTRACTED."""
    fake = FakeAIProvider(responses=[answer()])
    use_provider(fake)
    return fake
