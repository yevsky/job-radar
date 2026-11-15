from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import JobOffer, Technology
from app.schemas.job_offer import JobOfferFilters, JobOfferListItem, JobOfferPage, JobOfferRead


class OfferNotFoundError(Exception):
    """The offer doesn't exist, or it is someone else's private offer."""


class NotOfferOwnerError(Exception):
    """The offer is public, or added by someone else, so this user can't delete it."""


def visible_to(user_id: int) -> ColumnElement[bool]:
    """SQL condition: public offers, plus the private ones this user added."""
    return or_(JobOffer.owner_id.is_(None), JobOffer.owner_id == user_id)


def to_list_item(offer: JobOffer) -> JobOfferListItem:
    return JobOfferListItem(
        id=offer.id,
        title=offer.title,
        company_name=offer.company_name,
        location=offer.location,
        employment_type=offer.employment_type,
        experience_level=offer.experience_level,
        deadline=offer.deadline,
        technologies=sorted(t.name for t in offer.technologies),
    )


def list_job_offers(
    db: Session, user_id: int, limit: int, offset: int, filters: JobOfferFilters
) -> JobOfferPage:
    query = select(JobOffer).where(JobOffer.is_active, visible_to(user_id))

    for name in filters.technologies:
        query = query.where(JobOffer.technologies.any(func.lower(Technology.name) == name.lower()))
    if filters.location:
        query = query.where(JobOffer.location.icontains(filters.location, autoescape=True))
    if filters.experience_levels:
        query = query.where(JobOffer.experience_level.in_(filters.experience_levels))
    if filters.employment_types:
        query = query.where(JobOffer.employment_type.in_(filters.employment_types))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    offers = db.scalars(
        query.options(selectinload(JobOffer.technologies))
        .order_by(JobOffer.created_at.desc(), JobOffer.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return JobOfferPage(
        items=[to_list_item(offer) for offer in offers],
        total=total,
        limit=limit,
        offset=offset,
    )


def to_read(offer: JobOffer) -> JobOfferRead:
    return JobOfferRead(
        id=offer.id,
        title=offer.title,
        company_name=offer.company_name,
        location=offer.location,
        employment_type=offer.employment_type,
        experience_level=offer.experience_level,
        deadline=offer.deadline,
        technologies=sorted(t.name for t in offer.technologies),
        source=offer.source,
        url=offer.url,
        description=offer.description,
        is_active=offer.is_active,
        is_private=offer.owner_id is not None,
        last_seen_at=offer.last_seen_at,
        created_at=offer.created_at,
    )


def get_job_offer(db: Session, offer_id: int, user_id: int) -> JobOfferRead | None:
    offer = db.scalar(select(JobOffer).where(JobOffer.id == offer_id, visible_to(user_id)))
    if offer is None:
        return None
    return to_read(offer)


def delete_own_offer(db: Session, offer_id: int, user_id: int) -> None:
    """Delete a private offer the user added; raise if it isn't theirs."""
    offer = db.scalar(select(JobOffer).where(JobOffer.id == offer_id, visible_to(user_id)))
    if offer is None:
        raise OfferNotFoundError
    if offer.owner_id != user_id:
        raise NotOfferOwnerError
    db.delete(offer)
    db.commit()


def get_public_offer(db: Session, offer_id: int) -> JobOffer | None:
    """An offer everyone can see; private offers are left out, even for admins."""
    return db.scalar(select(JobOffer).where(JobOffer.id == offer_id, JobOffer.owner_id.is_(None)))


def set_job_offer_active(db: Session, offer_id: int, is_active: bool) -> JobOfferRead | None:
    """Show or hide a public offer in the list; return None if there is no such offer."""
    offer = get_public_offer(db, offer_id)
    if offer is None:
        return None
    offer.is_active = is_active
    db.commit()
    return to_read(offer)


def delete_job_offer(db: Session, offer_id: int) -> bool:
    """Delete a public offer and its technology links; return False if there is no such offer."""
    offer = get_public_offer(db, offer_id)
    if offer is None:
        return False
    db.delete(offer)
    db.commit()
    return True
