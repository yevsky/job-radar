from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.dependencies import DbSession
from app.dependencies import get_current_user
from app.schemas.job_offer import JobOfferPage, JobOfferRead
from app.services.job_offer import get_job_offer, list_job_offers

router = APIRouter(
    prefix='/job-offers', tags=['job-offers'], dependencies=[Depends(get_current_user)]
)


@router.get('', response_model=JobOfferPage)
def read_job_offers(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobOfferPage:
    return list_job_offers(db, limit, offset)


@router.get('/{offer_id}', response_model=JobOfferRead)
def read_job_offer(offer_id: int, db: DbSession) -> JobOfferRead:
    offer = get_job_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found')
    return offer
