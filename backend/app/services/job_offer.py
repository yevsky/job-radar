from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import JobOffer, Technology
from app.schemas.job_offer import JobOfferFilters, JobOfferListItem, JobOfferPage, JobOfferRead


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


def list_job_offers(db: Session, limit: int, offset: int, filters: JobOfferFilters) -> JobOfferPage:
    query = select(JobOffer).where(JobOffer.is_active)

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
        is_active=offer.is_active,
        last_seen_at=offer.last_seen_at,
        created_at=offer.created_at,
    )


def get_job_offer(db: Session, offer_id: int) -> JobOfferRead | None:
    offer = db.get(JobOffer, offer_id)
    if offer is None:
        return None
    return to_read(offer)
