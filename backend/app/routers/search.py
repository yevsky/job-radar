from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.db.dependencies import DbSession
from app.dependencies import CurrentUser, SearchSources
from app.models.enums import SourceKind
from app.schemas.job_offer import JobOfferRead
from app.schemas.search import SearchQuery, SearchResponse, SearchResult, SearchUsage
from app.services.job_offer import to_read
from app.services.job_offer_import import add_private_offer
from app.services.search import (
    EmptyQueryError,
    SearchLimitError,
    default_search_query,
    get_usage,
    run_search,
)

router = APIRouter(prefix='/search', tags=['search'])


@router.get('/defaults', response_model=SearchQuery)
def read_search_defaults(user: CurrentUser) -> SearchQuery:
    """The search form prefilled from your profile; change any field before searching."""
    return default_search_query(user)


@router.get('/usage', response_model=SearchUsage)
def read_search_usage(user: CurrentUser, db: DbSession) -> SearchUsage:
    """Your daily search limit and how many searches you have left today."""
    return get_usage(db, user)


@router.post('', response_model=SearchResponse)
def search_jobs(
    query: SearchQuery, user: CurrentUser, db: DbSession, sources: SearchSources
) -> SearchResponse:
    """Search every enabled source with the form. The results are returned, not saved."""
    try:
        return run_search(db, user, query, sources, settings.search_results_per_source)
    except EmptyQueryError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Add a position or at least one skill',
        ) from err
    except SearchLimitError as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Daily search limit reached, try again tomorrow',
        ) from err


@router.post('/results', response_model=JobOfferRead, status_code=status.HTTP_201_CREATED)
def save_search_result(
    data: SearchResult, db: DbSession, user: CurrentUser, response: Response
) -> JobOfferRead:
    """Keep a search result as an offer only you can see; a known link returns that offer."""
    offer, created = add_private_offer(
        db, data, user.id, source=SourceKind.SEARCH, found_via=data.found_via
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return to_read(offer)
