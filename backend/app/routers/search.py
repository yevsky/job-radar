from fastapi import APIRouter

from app.dependencies import CurrentUser
from app.schemas.search import SearchQuery
from app.services.search import default_search_query

router = APIRouter(prefix='/search', tags=['search'])


@router.get('/defaults', response_model=SearchQuery)
def read_search_defaults(user: CurrentUser) -> SearchQuery:
    """The search form prefilled from your profile; change any field before searching."""
    return default_search_query(user)
