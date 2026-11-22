from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.ai.base import AIProviderError
from app.ai.structured import AIOutputError
from app.db.dependencies import DbSession
from app.dependencies import AI, CurrentUser, get_current_user
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import JobOfferParseRequest, JobOfferParseResponse
from app.schemas.job_offer import JobOfferFilters, JobOfferImport, JobOfferPage, JobOfferRead
from app.services.job_offer import (
    NotOfferOwnerError,
    OfferNotFoundError,
    delete_own_offer,
    get_job_offer,
    list_job_offers,
    to_read,
)
from app.services.job_offer_import import add_private_offer
from app.services.offer_parsing import draft_offer

router = APIRouter(
    prefix='/job-offers', tags=['job-offers'], dependencies=[Depends(get_current_user)]
)


@router.get('', response_model=JobOfferPage)
def read_job_offers(
    db: DbSession,
    user: CurrentUser,
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
    return list_job_offers(db, user.id, limit, offset, filters)


@router.get('/{offer_id}', response_model=JobOfferRead)
def read_job_offer(offer_id: int, db: DbSession, user: CurrentUser) -> JobOfferRead:
    offer = get_job_offer(db, offer_id, user.id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found')
    return offer


@router.post('', response_model=JobOfferRead, status_code=status.HTTP_201_CREATED)
def create_job_offer(
    data: JobOfferImport, db: DbSession, user: CurrentUser, response: Response
) -> JobOfferRead:
    """Add an offer only you can see; a link that is already known returns that offer."""
    offer, created = add_private_offer(db, data, user.id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return to_read(offer)


@router.post('/parse', response_model=JobOfferParseResponse)
def parse_job_offer(data: JobOfferParseRequest, ai: AI) -> JobOfferParseResponse:
    """Read a pasted posting's fields with the AI. Saves nothing: check the fields, then
    save the offer with POST /job-offers."""
    try:
        return draft_offer(ai, data)
    except (AIProviderError, AIOutputError) as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider didn't answer, try again or fill the fields by hand",
        ) from err


@router.delete('/{offer_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_my_job_offer(offer_id: int, db: DbSession, user: CurrentUser) -> None:
    """Delete an offer you added yourself."""
    try:
        delete_own_offer(db, offer_id, user.id)
    except OfferNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found'
        ) from err
    except NotOfferOwnerError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='You can only delete offers you added yourself',
        ) from err
