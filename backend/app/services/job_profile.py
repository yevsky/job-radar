from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.job_offer import JobOffer
from app.schemas.job_offer import JobOfferListItem, JobOfferPage


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


def list_job_offers(db: Session, limit: int, offset: int) -> JobOfferPage:
    query = select(JobOffer).where(JobOffer.is_active)

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
