from fastapi import status
from fastapi.testclient import TestClient

from app.ai.fake import FakeAIProvider
from tests.conftest import UseProvider
from tests.helpers import auth_header

URL = '/admin/ai-provider'


def test_admin_sees_provider_model_and_that_it_works(
    api: TestClient, admin_token: str, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider())

    response = api.get(URL, headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'provider': 'fake', 'model': 'fake', 'base_url': None, 'ok': True}


def test_admin_sees_a_provider_that_doesnt_answer(
    api: TestClient, admin_token: str, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(fail=True))

    response = api.get(URL, headers=auth_header(admin_token))

    assert response.json()['ok'] is False


def test_normal_user_cannot_check_the_provider(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_anonymous_user_cannot_check_the_provider(api: TestClient) -> None:
    assert api.get(URL).status_code == status.HTTP_401_UNAUTHORIZED
