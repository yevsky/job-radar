from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.dependencies import CurrentUser, SearchSources, get_current_user
from app.schemas.search import SearchQuery, SearchResponse
from app.services.search import EmptyQueryError, default_search_query, run_search

router = APIRouter(prefix='/search', tags=['search'])


@router.get('/defaults', response_model=SearchQuery)
def read_search_defaults(user: CurrentUser) -> SearchQuery:
    """The search form prefilled from your profile; change any field before searching."""
    return default_search_query(user)


@router.post('', response_model=SearchResponse, dependencies=[Depends(get_current_user)])
def search_jobs(query: SearchQuery, sources: SearchSources) -> SearchResponse:
    """Search every enabled source with the form. The results are returned, not saved."""
    try:
        return run_search(query, sources, settings.search_results_per_source)
    except EmptyQueryError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Add a position or at least one skill',
        ) from err
