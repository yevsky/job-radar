from app.models import User
from app.schemas.search import (
    MAX_LOCATIONS,
    MAX_SKILLS,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SourceError,
)
from app.search_sources.base import SearchSource, SearchSourceError
from app.services.job_offer_import import normalize_url


class EmptyQueryError(Exception):
    """The search form has no position and no skills, so there is nothing to search for."""


def default_search_query(user: User) -> SearchQuery:
    """The search form prefilled from the profile: job fields only, never name, bio or email."""
    profile = user.profile
    return SearchQuery(
        position=profile.desired_position if profile else None,
        experience_level=profile.experience_level if profile else None,
        skills=[technology.name for technology in user.technologies][:MAX_SKILLS],
        locations=[preferred.location for preferred in user.preferred_locations][:MAX_LOCATIONS],
        employment_types=[
            preferred.employment_type for preferred in user.preferred_employment_types
        ],
    )


def run_search(query: SearchQuery, sources: list[SearchSource], limit: int) -> SearchResponse:
    """Ask every source, merge their results and return them. Nothing is saved.

    A source that fails is listed in errors and the others still count. A link found by
    two sources (same normalized URL) is returned once, from the first source.
    """
    if query.is_empty():
        raise EmptyQueryError

    results: list[SearchResult] = []
    errors: list[SourceError] = []
    seen_urls: set[str] = set()

    for source in sources:
        try:
            offers = source.search(query, limit)
        except SearchSourceError as err:
            errors.append(SourceError(source=source.name, message=str(err)))
            continue

        for offer in offers:
            url = normalize_url(str(offer.url))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(SearchResult(**offer.model_dump(), found_via=source.name))

    return SearchResponse(query=query.text(), results=results, errors=errors)
