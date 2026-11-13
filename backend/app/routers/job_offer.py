from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.dependencies import DbSession
from app.dependencies import get_current_user
from app.schemas.job_offer import JobOfferPage
from app.services.job_offer import list_job_offers

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
