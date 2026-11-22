from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.fake import FakeAIProvider
from app.models import Resume
from tests.helpers import auth_header
from tests.resumes.conftest import upload


def apply(api: TestClient, token: str, resume_id: int, body: dict[str, Any]) -> Any:
    return api.post(f'/resumes/{resume_id}/apply', json=body, headers=auth_header(token))


def profile(api: TestClient, token: str) -> dict[str, Any]:
    return dict(api.get('/profile/me', headers=auth_header(token)).json())


def fill_profile(api: TestClient, token: str) -> None:
    """A profile the user typed by hand."""
    headers = auth_header(token)
    api.put(
        '/profile/me',
        json={'first_name': 'Anna', 'bio': 'Likes hiking', 'desired_position': 'Data analyst'},
        headers=headers,
    )
    api.put('/profile/me/skills', json={'skills': ['SQL', 'python']}, headers=headers)
    api.put('/profile/me/locations', json={'locations': ['Warsaw']}, headers=headers)
    api.put('/profile/me/employment-types', json={'employment_types': ['b2b']}, headers=headers)


def cv_id(api: TestClient, token: str) -> int:
    return int(upload(api, token).json()['id'])


def test_everything_is_applied_to_an_empty_profile(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = cv_id(api, access_token)
    body = {
        'desired_position': 'Python developer',
        'experience_level': 'junior',
        'skills': ['Python', 'FastAPI'],
        'locations': ['Wroclaw'],
        'employment_types': ['full_time'],
    }

    response = apply(api, access_token, resume_id, body)

    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result['desired_position'] == 'Python developer'
    assert result['experience_level'] == 'junior'
    assert sorted(result['skills']) == ['FastAPI', 'Python']
    assert result['preferred_locations'] == ['Wroclaw']
    assert result['preferred_employment_types'] == ['full_time']
    stored = profile(api, access_token)
    assert stored['desired_position'] == 'Python developer'
    assert sorted(stored['skills']) == ['FastAPI', 'Python']


def test_only_the_sent_fields_change(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)
    resume_id = cv_id(api, access_token)

    result = apply(api, access_token, resume_id, {'experience_level': 'junior'}).json()

    assert result['experience_level'] == 'junior'
    assert result['desired_position'] == 'Data analyst'
    assert result['first_name'] == 'Anna'
    assert result['bio'] == 'Likes hiking'
    assert sorted(result['skills']) == ['SQL', 'python']
    assert result['preferred_locations'] == ['Warsaw']


def test_lists_are_merged_without_duplicates(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)
    resume_id = cv_id(api, access_token)

    result = apply(
        api,
        access_token,
        resume_id,
        {
            'skills': ['Python', 'FastAPI', 'fastapi'],  # 'python' is already there
            'locations': ['warsaw', 'Remote'],
            'employment_types': ['b2b', 'full_time'],
        },
    ).json()

    assert sorted(result['skills']) == ['FastAPI', 'SQL', 'python']  # the user's spelling stays
    assert result['preferred_locations'] == ['Warsaw', 'Remote']
    assert sorted(result['preferred_employment_types']) == ['b2b', 'full_time']


def test_position_is_replaced_and_can_be_cleared(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)
    resume_id = cv_id(api, access_token)

    replaced = apply(api, access_token, resume_id, {'desired_position': 'Python developer'})
    cleared = apply(api, access_token, resume_id, {'desired_position': None})

    assert replaced.json()['desired_position'] == 'Python developer'
    assert cleared.json()['desired_position'] is None


def test_going_over_the_skill_limit_returns_422_and_changes_nothing(
    api: TestClient, access_token: str, provider: FakeAIProvider, db: Session
) -> None:
    del provider
    fill_profile(api, access_token)  # 2 skills
    resume_id = cv_id(api, access_token)
    before = profile(api, access_token)

    response = apply(
        api,
        access_token,
        resume_id,
        {'desired_position': 'Python developer', 'skills': [f'Skill {n}' for n in range(49)]},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert 'skills' in response.json()['detail']
    after = profile(api, access_token)
    assert after['desired_position'] == before['desired_position']  # not even this changed
    assert sorted(after['skills']) == sorted(before['skills'])
    resume = db.get(Resume, resume_id)
    assert resume is not None
    assert resume.applied_to_profile_at is None


def test_going_over_the_location_limit_returns_422(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)  # 1 location
    resume_id = cv_id(api, access_token)

    response = apply(api, access_token, resume_id, {'locations': [f'City {n}' for n in range(10)]})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_applying_records_when(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = cv_id(api, access_token)

    apply(api, access_token, resume_id, {'skills': ['Python']})

    details = api.get(f'/resumes/{resume_id}', headers=auth_header(access_token)).json()
    assert details['applied_to_profile_at'] is not None


def test_summary_from_the_frontend_is_ignored(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = cv_id(api, access_token)

    response = apply(api, access_token, resume_id, {'summary': 'Junior dev', 'skills': ['Go']})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['bio'] is None


def test_invalid_values_return_422(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = cv_id(api, access_token)

    for body in (
        {'experience_level': 'expert'},
        {'employment_types': ['freelance']},
        {'skills': ['x' * 51]},
        {'desired_position': 'p' * 121},
    ):
        assert apply(api, access_token, resume_id, body).status_code == 422


def test_replace_mode_keeps_only_the_cvs_skills(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)  # SQL, python
    resume_id = cv_id(api, access_token)

    response = apply(
        api,
        access_token,
        resume_id,
        {'skills': ['Python', 'FastAPI', 'fastapi'], 'skills_mode': 'replace'},
    )

    assert response.status_code == status.HTTP_200_OK
    # SQL is gone; 'python' keeps the spelling the technologies table already has
    assert sorted(response.json()['skills']) == ['FastAPI', 'python']
    assert sorted(profile(api, access_token)['skills']) == ['FastAPI', 'python']


def test_replace_mode_leaves_the_other_lists_merged(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)  # Warsaw, b2b
    resume_id = cv_id(api, access_token)

    result = apply(
        api,
        access_token,
        resume_id,
        {'skills': ['Go'], 'locations': ['Wroclaw'], 'skills_mode': 'replace'},
    ).json()

    assert result['skills'] == ['Go']
    assert result['preferred_locations'] == ['Warsaw', 'Wroclaw']


def test_replace_mode_without_skills_changes_no_skills(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    fill_profile(api, access_token)
    resume_id = cv_id(api, access_token)

    result = apply(
        api, access_token, resume_id, {'desired_position': 'Go dev', 'skills_mode': 'replace'}
    ).json()

    assert sorted(result['skills']) == ['SQL', 'python']


def test_replace_mode_still_checks_the_limit(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    """Replacing with 51 skills fails like adding would: nothing changes."""
    del provider
    fill_profile(api, access_token)
    resume_id = cv_id(api, access_token)

    response = apply(
        api,
        access_token,
        resume_id,
        {'skills': [f'Skill {n}' for n in range(51)], 'skills_mode': 'replace'},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert sorted(profile(api, access_token)['skills']) == ['SQL', 'python']


def test_unknown_skills_mode_returns_422(
    api: TestClient, access_token: str, provider: FakeAIProvider
) -> None:
    del provider
    resume_id = cv_id(api, access_token)
    response = apply(api, access_token, resume_id, {'skills': ['Go'], 'skills_mode': 'swap'})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
