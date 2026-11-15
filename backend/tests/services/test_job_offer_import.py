from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import JobOffer, Technology
from app.models.enums import EmploymentType, SourceKind
from app.services.job_offer_import import import_offers
from tests.helpers import make_offer


def row(url: str = 'https://example.com/jobs/1', **overrides: Any) -> dict[str, Any]:
    """A valid import row; override any field to test one thing."""
    data: dict[str, Any] = {
        'title': 'Backend Developer',
        'company_name': 'Codesky',
        'url': url,
        'location': 'Wrocław',
        'employment_type': 'b2b',
        'experience_level': 'junior',
        'technologies': ['Python', 'FastAPI'],
    }
    data.update(overrides)
    return data


def offers_in_db(db: Session) -> list[JobOffer]:
    return list(db.scalars(select(JobOffer).order_by(JobOffer.id)).all())


def count_technologies(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Technology)) or 0


def test_valid_rows_create_offers(db: Session) -> None:
    report = import_offers(
        db,
        [row('https://example.com/jobs/1'), row('https://example.com/jobs/2')],
        SourceKind.MANUAL,
    )

    assert report.created == 2
    assert report.updated == 0
    assert report.skipped == 0
    assert report.errors == []
    offers = offers_in_db(db)
    assert len(offers) == 2
    first = offers[0]
    assert first.title == 'Backend Developer'
    assert first.source == SourceKind.MANUAL
    assert first.employment_type == EmploymentType.B2B
    assert first.is_active is True
    assert first.last_seen_at is not None
    assert sorted(t.name for t in first.technologies) == ['FastAPI', 'Python']


def test_empty_batch_does_nothing(db: Session) -> None:
    report = import_offers(db, [], SourceKind.MANUAL)

    assert report.model_dump() == {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    assert offers_in_db(db) == []


def test_importing_same_batch_again_updates_instead_of_creating(db: Session) -> None:
    rows = [row('https://example.com/jobs/1'), row('https://example.com/jobs/2')]
    import_offers(db, rows, SourceKind.MANUAL)
    first_seen = offers_in_db(db)[0].last_seen_at

    report = import_offers(db, rows, SourceKind.MANUAL)

    assert report.created == 0
    assert report.updated == 2
    offers = offers_in_db(db)
    assert len(offers) == 2
    assert first_seen is not None
    assert offers[0].last_seen_at is not None
    assert offers[0].last_seen_at > first_seen


def test_update_overwrites_fields_but_keeps_source(db: Session) -> None:
    import_offers(db, [row(title='Old title')], SourceKind.SEARCH)

    import_offers(db, [row(title='New title', technologies=['Go'])], SourceKind.MANUAL)

    offer = offers_in_db(db)[0]
    assert offer.title == 'New title'
    assert [t.name for t in offer.technologies] == ['Go']
    assert offer.source == SourceKind.SEARCH


def test_different_spellings_of_one_url_are_the_same_offer(db: Session) -> None:
    import_offers(db, [row('https://example.com/job/1')], SourceKind.MANUAL)

    report = import_offers(
        db, [row('https://Example.com/job/1/?utm_source=x#apply')], SourceKind.MANUAL
    )

    assert report.created == 0
    assert report.updated == 1
    offers = offers_in_db(db)
    assert len(offers) == 1
    assert offers[0].url == 'https://example.com/job/1'


def test_same_url_twice_in_one_batch_is_saved_once(db: Session) -> None:
    rows = [
        row('https://example.com/jobs/1'),
        row('https://example.com/jobs/1/?utm_source=newsletter'),
    ]

    report = import_offers(db, rows, SourceKind.MANUAL)

    assert report.created == 1
    assert report.skipped == 1
    assert len(offers_in_db(db)) == 1


def test_invalid_rows_are_reported_and_valid_rows_still_import(db: Session) -> None:
    missing_title = row('https://example.com/jobs/2')
    del missing_title['title']
    rows = [
        row('https://example.com/jobs/1'),
        missing_title,
        row('not a url'),
        row('https://example.com/jobs/4', employment_type='freelance'),
        row('https://example.com/jobs/5'),
    ]

    report = import_offers(db, rows, SourceKind.MANUAL)

    assert report.created == 2
    assert [error.row for error in report.errors] == [2, 3, 4]
    assert 'title' in report.errors[0].message
    assert 'url' in report.errors[1].message
    assert 'employment_type' in report.errors[2].message
    assert [o.url for o in offers_in_db(db)] == [
        'https://example.com/jobs/1',
        'https://example.com/jobs/5',
    ]


def test_blank_title_is_an_error(db: Session) -> None:
    report = import_offers(db, [row(title='   ')], SourceKind.MANUAL)

    assert report.created == 0
    assert report.errors[0].row == 1


def test_text_fields_are_trimmed(db: Session) -> None:
    import_offers(
        db, [row(title='  Backend Developer ', company_name=' Codesky  ')], SourceKind.MANUAL
    )

    offer = offers_in_db(db)[0]
    assert offer.title == 'Backend Developer'
    assert offer.company_name == 'Codesky'


def test_inactive_offer_becomes_active_again(db: Session) -> None:
    db.add(make_offer('https://example.com/jobs/1', is_active=False))
    db.flush()

    report = import_offers(db, [row('https://example.com/jobs/1')], SourceKind.MANUAL)

    assert report.updated == 1
    assert offers_in_db(db)[0].is_active is True


def test_existing_technology_is_reused_ignoring_case(db: Session) -> None:
    db.add(Technology(name='Python'))
    db.flush()

    import_offers(db, [row(technologies=['python', 'FastAPI'])], SourceKind.MANUAL)

    offer = offers_in_db(db)[0]
    assert sorted(t.name for t in offer.technologies) == ['FastAPI', 'Python']
    assert count_technologies(db) == 2


def test_new_technology_shared_by_two_rows_is_created_once(db: Session) -> None:
    rows = [
        row('https://example.com/jobs/1', technologies=['Rust']),
        row('https://example.com/jobs/2', technologies=['rust']),
    ]

    report = import_offers(db, rows, SourceKind.MANUAL)

    assert report.created == 2
    assert count_technologies(db) == 1


def test_technology_names_are_cleaned(db: Session) -> None:
    import_offers(
        db, [row(technologies=[' Python ', '', '  ', 'python', 'Docker'])], SourceKind.MANUAL
    )

    offer = offers_in_db(db)[0]
    assert sorted(t.name for t in offer.technologies) == ['Docker', 'Python']


def test_optional_fields_can_be_left_out(db: Session) -> None:
    minimal = {'title': 'Tester', 'company_name': 'Codesky', 'url': 'https://example.com/jobs/9'}

    report = import_offers(db, [minimal], SourceKind.MANUAL)

    assert report.created == 1
    offer = offers_in_db(db)[0]
    assert offer.location is None
    assert offer.technologies == []


def test_deadline_is_stored(db: Session) -> None:
    import_offers(db, [row(deadline='2026-12-31T23:59:00Z')], SourceKind.MANUAL)

    assert offers_in_db(db)[0].deadline == datetime(2026, 12, 31, 23, 59, tzinfo=UTC)
