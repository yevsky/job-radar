import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import SourceKind
from app.schemas.job_offer import JobOfferImport
from app.scripts.seed import SEED_FILE, seed_offers
from app.services.job_offer_import import normalize_url
from tests.helpers import auth_header


@pytest.fixture(scope='module')
def rows() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(SEED_FILE.read_text(encoding='utf-8'))
    return data


# --- the file itself ------------------------------------------------------------------


def test_seed_file_has_30_to_50_offers(rows: list[dict[str, Any]]) -> None:
    assert 30 <= len(rows) <= 50


def test_every_seed_offer_is_valid(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        JobOfferImport.model_validate(row)  # raises if a row is invalid


def test_seed_urls_are_unique_after_normalizing(rows: list[dict[str, Any]]) -> None:
    urls = [normalize_url(row['url']) for row in rows]

    assert len(set(urls)) == len(urls)


def test_every_seed_offer_has_a_description(rows: list[dict[str, Any]]) -> None:
    assert all(row.get('description') for row in rows)


def test_seed_offers_cover_every_city_and_remote(rows: list[dict[str, Any]]) -> None:
    locations = {row['location'] for row in rows}

    assert {'Wrocław, PL', 'Warszawa, PL', 'Kraków, PL', 'Remote'} <= locations


# --- importing it ---------------------------------------------------------------------


def test_seed_creates_all_offers_as_posted(db: Session, rows: list[dict[str, Any]]) -> None:
    report = seed_offers(db)

    assert report.created == len(rows)
    assert report.errors == []
    offers = db.scalars(select(JobOffer)).all()
    assert len(offers) == len(rows)
    assert {offer.source for offer in offers} == {SourceKind.POSTED}
    assert all(offer.owner_id is None for offer in offers)
    assert all(offer.description for offer in offers)


def test_seeding_twice_creates_no_duplicates(db: Session, rows: list[dict[str, Any]]) -> None:
    seed_offers(db)

    report = seed_offers(db)

    assert report.created == 0
    assert report.updated == len(rows)
    assert len(db.scalars(select(JobOffer)).all()) == len(rows)


@pytest.mark.parametrize(
    ('params', 'check'),
    [
        ({'technology': 'python'}, lambda offer: 'Python' in offer['technologies']),
        ({'location': 'remote'}, lambda offer: offer['location'] == 'Remote'),
        ({'experience_level': 'junior'}, lambda offer: offer['experience_level'] == 'junior'),
    ],
    ids=['technology', 'location', 'level'],
)
def test_filters_find_seeded_offers(
    api: TestClient, access_token: str, db: Session, params: dict[str, str], check: Any
) -> None:
    seed_offers(db)

    body = api.get(
        '/job-offers', params={**params, 'limit': 100}, headers=auth_header(access_token)
    ).json()

    assert body['total'] > 0
    assert all(check(offer) for offer in body['items'])
