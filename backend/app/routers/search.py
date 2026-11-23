from fastapi import APIRouter, HTTPException, Response, status

from app.ai.base import AIProviderError
from app.ai.structured import AIOutputError
from app.core.config import settings
from app.db.dependencies import DbSession
from app.dependencies import AI, CurrentUser, EnabledSearchSources, Pages, SearchSources
from app.models.enums import SourceKind
from app.schemas.analysis import AnalysisResult, SearchAnalysisRequest
from app.schemas.search import (
    SavedSearchResult,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchSourcesRead,
    SearchSourcesUpdate,
    SearchUsage,
)
from app.services.ai_analysis import EmptyProfileError, analyse_search_result
from app.services.job_offer import to_read
from app.services.job_offer_import import add_private_offer
from app.services.offer_parsing import enrich_saved_offer
from app.services.resume import ResumeNotFoundError
from app.services.search import (
    EmptyQueryError,
    NoSourcesError,
    SearchLimitError,
    UnknownSourceError,
    default_search_query,
    get_source_choice,
    get_usage,
    run_search,
    set_source_choice,
    switched_off,
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
def read_search_sources(
    user: CurrentUser, db: DbSession, sources: EnabledSearchSources, every: SearchSources
) -> SearchSourcesRead:
    """The sources you can search with, which of them you chose, and which an admin
    switched off for everyone (`turned_off`)."""
    off = switched_off(db)
    return get_source_choice(user, sources, [s.name for s in every if s.name in off])


@router.put('/sources', response_model=SearchSourcesRead)
def update_search_sources(
    data: SearchSourcesUpdate,
    user: CurrentUser,
    db: DbSession,
    sources: EnabledSearchSources,
    every: SearchSources,
) -> SearchSourcesRead:
    """Choose which sources your searches ask; null asks all of them again."""
    try:
        set_source_choice(db, user, data.sources, sources)
    except UnknownSourceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Unknown search source: {", ".join(err.names)}',
        ) from err
    return read_search_sources(user, db, sources, every)


@router.post('', response_model=SearchResponse)
def search_jobs(
    query: SearchQuery, user: CurrentUser, db: DbSession, sources: EnabledSearchSources
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
    except NoSourcesError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Search is switched off by an admin right now',
        ) from err


@router.post('/results', response_model=SavedSearchResult, status_code=status.HTTP_201_CREATED)
def save_search_result(
    data: SearchResult,
    db: DbSession,
    user: CurrentUser,
    response: Response,
    ai: AI,
    pages: Pages,
) -> SavedSearchResult:
    """Keep a search result as an offer only you can see; a known link returns that offer.

    A new offer's empty fields (location, level, technologies, ...) are filled by the AI
    from the full posting page. If that fails, the offer is still saved, with enriched false.
    """
    offer, created = add_private_offer(
        db, data, user.id, source=SourceKind.SEARCH, found_via=data.found_via
    )
    enriched = False
    if not created:
        response.status_code = status.HTTP_200_OK
    elif settings.ai_enrich_saved_results:
        enriched = enrich_saved_offer(db, offer, ai, pages)
    return SavedSearchResult(**to_read(offer).model_dump(), enriched=enriched)


@router.post('/analysis', response_model=AnalysisResult)
def analyse_search_result_route(
    data: SearchAnalysisRequest, db: DbSession, user: CurrentUser, ai: AI
) -> AnalysisResult:
    """Match a search result against your profile (and a CV of yours, if given).

    Nothing is stored, like the search itself. Save the result and use
    POST /job-offers/{id}/analysis to keep an analysis.
    """
    try:
        return analyse_search_result(db, ai, user, data.result, data.resume_id)
    except ResumeNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='CV not found') from err
    except EmptyProfileError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Fill your profile first: add a desired position or a skill',
        ) from err
    except (AIProviderError, AIOutputError) as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider didn't answer, try again",
        ) from err
