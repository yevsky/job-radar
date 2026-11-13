import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import JobOffer, Technology
from app.models.enums import SourceKind
from app.models.job_offer import job_offer_technologies


def make_offer(url: str = 'https://example.com/jobs/1', **overrides: object) -> JobOffer:
    """A valid job offer with only the required fields filled in."""
    fields: dict[str, object] = {
        'title': 'Backend Developer',
        'company_name': 'Acme',
        'source': SourceKind.MANUAL,
        'url': url,
    }
    fields.update(overrides)
    return JobOffer(**fields)


def count_links(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(job_offer_technologies)) or 0


def test_new_offer_is_active_by_default(db: Session) -> None:
    offer = make_offer()
    db.add(offer)
    db.flush()

    assert offer.is_active is True


def test_deleting_offer_deletes_technology_links_but_keeps_technologies(db: Session) -> None:
    offer = make_offer(technologies=[Technology(name='Python'), Technology(name='Docker')])
    db.add(offer)
    db.flush()
    assert count_links(db) == 2

    db.delete(offer)
    db.flush()

    assert count_links(db) == 0
    names = db.scalars(select(Technology.name).order_by(Technology.name)).all()
    assert names == ['Docker', 'Python']


def test_two_offers_cannot_share_a_url(db: Session) -> None:
    db.add_all([make_offer(), make_offer(title='Another title')])

    with pytest.raises(IntegrityError):
        db.flush()
