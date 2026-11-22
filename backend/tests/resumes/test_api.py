import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.models import Resume
from app.services.resume import MAX_RESUME_BYTES, MAX_RESUMES_PER_USER
from tests.conftest import UseProvider, register_and_login
from tests.helpers import auth_header
from tests.resumes.conftest import CV_PDF, CV_TEXT, EXTRACTED, answer, upload
from tests.resumes.pdf import make_pdf


def count_resumes(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Resume)) or 0


@pytest.fixture
def other_token(api: TestClient) -> str:
    _, token = register_and_login(api, 'other@example.com')
    return token


def test_upload_without_token_returns_401(api: TestClient) -> None:
    response = api.post('/resumes', files={'file': ('cv.pdf', CV_PDF, 'application/pdf')})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_upload_stores_the_text_and_what_the_ai_read(
    api: TestClient, access_token: str, provider: FakeAIProvider, db: Session
) -> None:
    response = upload(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['label'] == 'Backend CV'
    assert body['file_name'] == 'anna-cv.pdf'
    assert body['extracted'] == EXTRACTED
    assert body['extracted_with'] == 'fake/fake'
    assert body['applied_to_profile_at'] is None
    assert 'text' not in body  # the list stays small; GET /resumes/{id} has it
    resume = db.get(Resume, body['id'])
    assert resume is not None
    assert resume.text == CV_TEXT
    assert len(provider.calls) == 1


def test_the_ai_gets_the_cv_inside_the_untrusted_block(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    upload(api, access_token)

    [messages] = provider.calls
    assert messages[1].content == f'<resume>\n{CV_TEXT}\n</resume>'


def test_nothing_goes_into_the_profile_on_upload(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    upload(api, access_token)

    profile = api.get('/profile/me', headers=auth_header(access_token)).json()
    assert profile['skills'] == []
    assert profile['desired_position'] is None


def test_ai_down_still_stores_the_cv_without_extracted_data(
    api: TestClient, access_token: str, use_provider: UseProvider, db: Session
) -> None:
    use_provider(FakeAIProvider(fail=True))

    response = upload(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['extracted'] is None
    assert response.json()['extracted_with'] is None
    assert count_resumes(db) == 1


def test_bad_ai_answers_still_store_the_cv(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(responses=['I cannot read CVs.']))

    response = upload(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['extracted'] is None


def test_extract_again_after_a_failure(
    api: TestClient, access_token: str, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(fail=True))
    resume_id = upload(api, access_token).json()['id']
    use_provider(FakeAIProvider(responses=[answer()]))

    response = api.post(f'/resumes/{resume_id}/extract', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['extracted'] == EXTRACTED


def test_extract_again_with_the_ai_down_returns_502_and_keeps_the_old_data(
    api: TestClient, access_token: str, provider: FakeAIProvider, use_provider: UseProvider
) -> None:
    del provider
    resume_id = upload(api, access_token).json()['id']
    use_provider(FakeAIProvider(fail=True))

    response = api.post(f'/resumes/{resume_id}/extract', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    details = api.get(f'/resumes/{resume_id}', headers=auth_header(access_token)).json()
    assert details['extracted'] == EXTRACTED


@pytest.mark.parametrize(
    ('content', 'content_type', 'message'),
    [
        (b'Hello', 'text/plain', 'not a PDF'),
        (b'Hello, not really a PDF', 'application/pdf', 'not a PDF'),  # lies about its type
        (b'%PDF-1.4 garbage', 'application/pdf', 'could not be read'),
        (make_pdf(), 'application/pdf', 'no text'),
        (b'%PDF' + b'0' * MAX_RESUME_BYTES, 'application/pdf', 'larger than 5 MB'),
    ],
    ids=['text-file', 'fake-pdf', 'broken', 'scanned', 'too-big'],
)
def test_bad_files_return_422_and_call_no_ai(
    api: TestClient,
    access_token: str,
    provider: FakeAIProvider,
    db: Session,
    content: bytes,
    content_type: str,
    message: str,
) -> None:
    response = upload(api, access_token, content=content, content_type=content_type)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert message in response.json()['detail']
    assert provider.calls == []
    assert count_resumes(db) == 0


@pytest.mark.parametrize('label', ['', '   ', 'x' * 101])
def test_label_is_required_and_short(
    api: TestClient, access_token: str, provider: FakeAIProvider, label: str
) -> None:
    del provider
    response = upload(api, access_token, label=label)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_same_label_twice_returns_409(
    api: TestClient, access_token: str, provider: FakeAIProvider, db: Session
) -> None:
    upload(api, access_token)

    response = upload(api, access_token, label=' Backend CV ')

    assert response.status_code == status.HTTP_409_CONFLICT
    assert len(provider.calls) == 1
    assert count_resumes(db) == 1


def test_two_users_can_use_the_same_label(
    api: TestClient, access_token: str, other_token: str, provider: FakeAIProvider
) -> None:
    del provider
    assert upload(api, access_token).status_code == status.HTTP_201_CREATED
    assert upload(api, other_token).status_code == status.HTTP_201_CREATED


def test_at_most_ten_cvs(
    api: TestClient, access_token: str, provider: FakeAIProvider, db: Session
) -> None:
    del provider
    for number in range(MAX_RESUMES_PER_USER):
        assert upload(api, access_token, label=f'CV {number}').status_code == 201

    response = upload(api, access_token, label='One more')

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert 'at most 10' in response.json()['detail']
    assert count_resumes(db) == MAX_RESUMES_PER_USER


def test_list_shows_only_my_cvs_newest_first(
    api: TestClient, access_token: str, other_token: str, provider: FakeAIProvider
) -> None:
    del provider
    upload(api, access_token, label='Backend CV')
    upload(api, access_token, label='Data CV')
    upload(api, other_token, label='Their CV')

    response = api.get('/resumes', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert [resume['label'] for resume in response.json()] == ['Data CV', 'Backend CV']


def test_details_include_the_text(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = upload(api, access_token).json()['id']

    response = api.get(f'/resumes/{resume_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['text'] == CV_TEXT


def test_another_users_cv_is_not_found(
    api: TestClient, access_token: str, other_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = upload(api, access_token).json()['id']
    headers = auth_header(other_token)

    assert api.get(f'/resumes/{resume_id}', headers=headers).status_code == 404
    assert api.post(f'/resumes/{resume_id}/extract', headers=headers).status_code == 404
    assert api.post(f'/resumes/{resume_id}/apply', json={}, headers=headers).status_code == 404
    assert api.delete(f'/resumes/{resume_id}', headers=headers).status_code == 404
    assert api.get('/resumes/999999', headers=auth_header(access_token)).status_code == 404


def test_delete_my_cv(
    api: TestClient, access_token: str, provider: FakeAIProvider, db: Session
) -> None:
    del provider
    resume_id = upload(api, access_token).json()['id']

    response = api.delete(f'/resumes/{resume_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert count_resumes(db) == 0
