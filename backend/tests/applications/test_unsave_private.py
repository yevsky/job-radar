"""Unsaving an offer only you can see deletes it, with everything run on it."""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AiAnalysis, Application, JobOffer
from app.models.enums import SourceKind
from tests.helpers import auth_header

URL = '/saved-jobs'


def add_private(api: TestClient, token: str, url: str = 'https://example.com/jobs/kept') -> int:
    body = {'title': 'Kept from search', 'company_name': 'Codesky', 'url': url}
    response = api.post('/job-offers', json=body, headers=auth_header(token))
    assert response.status_code == status.HTTP_201_CREATED
    return int(response.json()['id'])


def save(api: TestClient, token: str, offer_id: int) -> None:
    response = api.post(URL, json={'job_offer_id': offer_id}, headers=auth_header(token))
    assert response.status_code == status.HTTP_201_CREATED


def run_analysis_and_summary(db: Session, offer_id: int, user_id: int) -> None:
    """What the user ran on the offer before unsaving it."""
    db.add(
        AiAnalysis(
            user_id=user_id,
            job_offer_id=offer_id,
            score=70,
            breakdown={'skills': 30},
            summary='Good match.',
            reasons=['Python'],
            red_flags=[],
            matched_skills=['Python'],
            missing_skills=[],
            provider='fake',
            model='fake',
            prompt_version='analysis-v2',
        )
    )
    offer = db.get(JobOffer, offer_id)
    assert offer is not None
    offer.summary = {'overview': 'A backend role.'}
    db.flush()


def count(db: Session, model: type[AiAnalysis] | type[Application], offer_id: int) -> int:
    return (
        db.scalar(select(func.count()).select_from(model).where(model.job_offer_id == offer_id))
        or 0
    )


def test_unsaving_your_own_offer_deletes_it_and_what_was_run_on_it(
    api: TestClient, db: Session, access_token: str, registered_user_id: int
) -> None:
    offer_id = add_private(api, access_token)
    save(api, access_token, offer_id)
    run_analysis_and_summary(db, offer_id, registered_user_id)

    response = api.delete(f'{URL}/{offer_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    db.expire_all()
    assert db.get(JobOffer, offer_id) is None
    assert count(db, AiAnalysis, offer_id) == 0
    assert count(db, Application, offer_id) == 0
    assert api.get('/job-offers/mine', headers=auth_header(access_token)).json() == []
    offer = api.get(f'/job-offers/{offer_id}', headers=auth_header(access_token))
    assert offer.status_code == status.HTTP_404_NOT_FOUND


def test_offer_kept_from_a_search_is_deleted_too(
    api: TestClient, db: Session, access_token: str
) -> None:
    offer_id = add_private(api, access_token)
    offer = db.get(JobOffer, offer_id)
    assert offer is not None
    offer.source = SourceKind.SEARCH
    db.flush()
    save(api, access_token, offer_id)

    api.delete(f'{URL}/{offer_id}', headers=auth_header(access_token))

    db.expire_all()
    assert db.get(JobOffer, offer_id) is None


def test_unsaving_a_job_board_offer_keeps_the_offer(
    api: TestClient, db: Session, access_token: str, offer: JobOffer
) -> None:
    save(api, access_token, offer.id)

    response = api.delete(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    db.expire_all()
    assert db.get(JobOffer, offer.id) is not None
    assert count(db, Application, offer.id) == 0
    still_there = api.get(f'/job-offers/{offer.id}', headers=auth_header(access_token))
    assert still_there.status_code == status.HTTP_200_OK


def test_your_offer_you_applied_to_is_not_deleted(
    api: TestClient, db: Session, access_token: str
) -> None:
    offer_id = add_private(api, access_token)
    body = {'job_offer_id': offer_id, 'status': 'applied'}
    api.post('/applications', json=body, headers=auth_header(access_token))

    response = api.delete(f'{URL}/{offer_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    db.expire_all()
    assert db.get(JobOffer, offer_id) is not None


def test_someone_elses_offer_cannot_be_unsaved(
    api: TestClient, db: Session, access_token: str, other_token: str
) -> None:
    offer_id = add_private(api, other_token)
    save(api, other_token, offer_id)

    response = api.delete(f'{URL}/{offer_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    db.expire_all()
    assert db.get(JobOffer, offer_id) is not None
