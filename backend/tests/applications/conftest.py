import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobOffer
from tests.conftest import register_and_login
from tests.helpers import make_offer


@pytest.fixture
def offer(db: Session) -> JobOffer:
    """A public offer everyone can see."""
    offer = make_offer('https://example.com/jobs/1', title='Python Developer')
    db.add(offer)
    db.flush()
    return offer


@pytest.fixture
def second_offer(db: Session) -> JobOffer:
    offer = make_offer(
        'https://example.com/jobs/2', title='Data Engineer', company_name='Northwind'
    )
    db.add(offer)
    db.flush()
    return offer


@pytest.fixture
def other_token(api: TestClient) -> str:
    _, token = register_and_login(api, 'other@example.com')
    return token
