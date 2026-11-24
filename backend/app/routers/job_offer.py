from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.ai.base import AIProviderError
from app.ai.structured import AIOutputError
from app.db.dependencies import DbSession
from app.dependencies import AI, CurrentUser, get_current_user
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import JobOfferParseRequest, JobOfferParseResponse, OfferSummaryRead
from app.schemas.analysis import AiAnalysisRead, AnalysisRequest
from app.schemas.job_offer import (
    JobOfferFilters,
    JobOfferImport,
    JobOfferPage,
    JobOfferRead,
    MyOfferItem,
)
from app.services.ai_analysis import EmptyProfileError, analyse_offer, latest_analysis
from app.services.job_offer import (
    NotOfferOwnerError,
    OfferNotFoundError,
    delete_own_offer,
    get_job_offer,
    list_job_offers,
    list_my_offers,
    to_read,
)
from app.services.job_offer_import import add_private_offer
from app.services.offer_parsing import draft_offer
from app.services.offer_summary import (
    NoDescriptionError,
    get_summary,
    summarise_offer,
)
from app.services.resume import ResumeNotFoundError

router = APIRouter(
    prefix='/job-offers', tags=['job-offers'], dependencies=[Depends(get_current_user)]
)

OFFER_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found')
CV_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='CV not found')
EMPTY_PROFILE = HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    detail='Fill your profile first: add a desired position or a skill',
)
AI_FAILED = HTTPException(
    status_code=status.HTTP_502_BAD_GATEWAY, detail="The AI provider didn't answer, try again"
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
    return list_job_offers(db, user.id, limit, offset, filters, public_only=True)


@router.get('/mine', response_model=list[MyOfferItem])
def read_my_offers(db: DbSession, user: CurrentUser) -> list[MyOfferItem]:
    """Offers you added yourself (by hand, from search or from the browser) and public
    offers you saved or applied to, newest first."""
    return list_my_offers(db, user.id)


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


@router.post(
    '/{offer_id}/analysis', response_model=AiAnalysisRead, status_code=status.HTTP_201_CREATED
)
def run_offer_analysis(
    offer_id: int, data: AnalysisRequest, db: DbSession, user: CurrentUser, ai: AI
) -> AiAnalysisRead:
    """Match the offer against your profile (and a CV of yours, if given) and keep the result.

    Every run adds a new analysis; GET returns the newest.
    """
    try:
        row = analyse_offer(db, ai, user, offer_id, data.resume_id)
    except OfferNotFoundError as err:
        raise OFFER_NOT_FOUND from err
    except ResumeNotFoundError as err:
        raise CV_NOT_FOUND from err
    except EmptyProfileError as err:
        raise EMPTY_PROFILE from err
    except (AIProviderError, AIOutputError) as err:
        raise AI_FAILED from err
    return AiAnalysisRead.model_validate(row)


@router.get('/{offer_id}/analysis', response_model=AiAnalysisRead)
def read_offer_analysis(offer_id: int, db: DbSession, user: CurrentUser) -> AiAnalysisRead:
    """Your newest analysis of the offer."""
    try:
        row = latest_analysis(db, user.id, offer_id)
    except OfferNotFoundError as err:
        raise OFFER_NOT_FOUND from err
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No analysis yet')
    return AiAnalysisRead.model_validate(row)


@router.post(
    '/{offer_id}/summary', response_model=OfferSummaryRead, status_code=status.HTTP_201_CREATED
)
def run_offer_summary(offer_id: int, db: DbSession, user: CurrentUser, ai: AI) -> OfferSummaryRead:
    """Summarise the posting with the AI and keep the summary on the offer.

    One summary per offer, shared by everyone who can see it; running again replaces it.
    """
    try:
        return summarise_offer(db, ai, user.id, offer_id)
    except OfferNotFoundError as err:
        raise OFFER_NOT_FOUND from err
    except NoDescriptionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='This offer has no description to summarise. Open the original posting.',
        ) from err
    except (AIProviderError, AIOutputError) as err:
        raise AI_FAILED from err


@router.get('/{offer_id}/summary', response_model=OfferSummaryRead)
def read_offer_summary(offer_id: int, db: DbSession, user: CurrentUser) -> OfferSummaryRead:
    """The offer's AI summary; 404 if nobody has summarised it yet."""
    try:
        summary = get_summary(db, user.id, offer_id)
    except OfferNotFoundError as err:
        raise OFFER_NOT_FOUND from err
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No summary yet')
    return summary
