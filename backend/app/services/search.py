from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import SearchRun, User
from app.schemas.search import (
    MAX_LOCATIONS,
    MAX_SKILLS,
    SearchLimitRead,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchUsage,
    SourceError,
)
from app.search_sources.base import SearchSource, SearchSourceError
from app.services.job_offer_import import normalize_url


class EmptyQueryError(Exception):
    """The search form has no position and no skills, so there is nothing to search for."""


class SearchLimitError(Exception):
    """The user has used all of today's searches."""


class UserNotFoundError(Exception):
    """No user with this id."""


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


def daily_limit(user: User) -> int:
    """The user's own limit if an admin set one, otherwise the default from settings."""
    if user.search_daily_limit is not None:
        return user.search_daily_limit
    return settings.search_daily_limit


def searches_today(db: Session, user_id: int) -> int:
    """How many searches the user has run since midnight UTC today."""
    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.scalar(
        select(func.count())
        .select_from(SearchRun)
        .where(SearchRun.user_id == user_id, SearchRun.created_at >= midnight)
    )
    return count or 0


def get_usage(db: Session, user: User) -> SearchUsage:
    limit = daily_limit(user)
    used = searches_today(db, user.id)
    return SearchUsage(daily_limit=limit, used_today=used, left_today=max(limit - used, 0))


def collect_results(
    query: SearchQuery, sources: list[SearchSource], limit: int
) -> tuple[list[SearchResult], list[SourceError]]:
    """Ask every source and merge the answers.

    A source that fails is listed in errors and the others still count. A link found by
    two sources (same normalized URL) is returned once, from the first source.
    """
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

    return results, errors


def run_search(
    db: Session, user: User, query: SearchQuery, sources: list[SearchSource], limit: int
) -> SearchResponse:
    """Run one search for the user, within their daily limit. Results are not saved.

    Only a small SearchRun row (who, when, how many results) is stored, to count searches.
    """
    if query.is_empty():
        raise EmptyQueryError

    usage = get_usage(db, user)
    if usage.left_today == 0:
        raise SearchLimitError  # checked before any source is called, so it costs nothing

    results, errors = collect_results(query, sources, limit)

    db.add(SearchRun(user_id=user.id, result_count=len(results)))
    db.commit()

    return SearchResponse(
        query=query.text(),
        results=results,
        errors=errors,
        searches_left_today=usage.left_today - 1,
    )


def to_limit_read(user: User) -> SearchLimitRead:
    return SearchLimitRead(
        user_id=user.id,
        search_daily_limit=user.search_daily_limit,
        effective_limit=daily_limit(user),
    )


def set_search_limit(db: Session, user_id: int, limit: int | None) -> SearchLimitRead:
    """Give one user their own daily limit, or None to use the default again."""
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    user.search_daily_limit = limit
    db.commit()
    return to_limit_read(user)
