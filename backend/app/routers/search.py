from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.db.dependencies import DbSession
from app.dependencies import CurrentUser, SearchSources
from app.models.enums import SourceKind
from app.schemas.job_offer import JobOfferRead
from app.schemas.search import (
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchSourcesRead,
    SearchSourcesUpdate,
    SearchUsage,
)
from app.services.job_offer import to_read
from app.services.job_offer_import import add_private_offer
from app.services.search import (
    EmptyQueryError,
    SearchLimitError,
    UnknownSourceError,
    default_search_query,
    get_source_choice,
    get_usage,
    run_search,
    set_source_choice,
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


@router.get('/sources', response_model=SearchSourcesRead)
def read_search_sources(user: CurrentUser, sources: SearchSources) -> SearchSourcesRead:
    """The sources you can search with, and which of them you chose."""
    return get_source_choice(user, sources)


@router.put('/sources', response_model=SearchSourcesRead)
def update_search_sources(
    data: SearchSourcesUpdate, user: CurrentUser, db: DbSession, sources: SearchSources
) -> SearchSourcesRead:
    """Choose which sources your searches ask; null asks all of them again."""
    try:
        return set_source_choice(db, user, data.sources, sources)
    except UnknownSourceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Unknown search source: {", ".join(err.names)}',
        ) from err


@router.post('', response_model=SearchResponse)
def search_jobs(
    query: SearchQuery, user: CurrentUser, db: DbSession, sources: SearchSources
) -> SearchResponse:
    """Search your chosen sources (all, by default) with the form. Results are not saved.

    `page` asks for the next results of the same form; only page 1 counts toward the limit.
    """
    try:
        return run_search(db, user, query, sources, settings.search_results_per_source)
    except EmptyQueryError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Add a position to search for',
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
