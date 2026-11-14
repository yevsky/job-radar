from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.dependencies import DbSession
from app.dependencies import get_current_user
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.job_offer import JobOfferFilters, JobOfferPage, JobOfferRead
from app.services.job_offer import get_job_offer, list_job_offers

router = APIRouter(
    prefix='/job-offers', tags=['job-offers'], dependencies=[Depends(get_current_user)]
)


@router.get('', response_model=JobOfferPage)
def read_job_offers(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    technology: Annotated[list[str] | None, Query()] = None,
    location: Annotated[str | None, Query(max_length=100)] = None,
    experience_level: Annotated[list[ExperienceLevel] | None, Query()] = None,
    employment_type: Annotated[list[EmploymentType] | None, Query()] = None,
) -> JobOfferPage:
    filters = JobOfferFilters(
        technologies=technology or [],
        location=location,
        experience_levels=experience_level or [],
        employment_types=employment_type or [],
    )
    return list_job_offers(db, limit, offset, filters)


@router.get('/{offer_id}', response_model=JobOfferRead)
def read_job_offer(offer_id: int, db: DbSession) -> JobOfferRead:
    offer = get_job_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found')
    return offer
