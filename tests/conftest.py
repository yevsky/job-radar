from collections.abc import Generator

import pytest
from backend.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
