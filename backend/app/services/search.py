from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.levels import fits_level
from app.models import SearchRun, User
from app.schemas.search import (
    MAX_LOCATIONS,
    MAX_SKILLS,
    SearchLimitRead,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchSourcesRead,
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


class UnknownSourceError(Exception):
    """The user chose a source the app doesn't have turned on."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(names)
        self.names = names


def chosen_sources(user: User, sources: list[SearchSource]) -> list[SearchSource]:
    """The enabled sources the user chose, in the app's order; all of them if none is left."""
    if not user.search_sources:
        return sources
    chosen = [source for source in sources if source.name in user.search_sources]
    return chosen or sources  # an admin may have turned off every source the user chose


def get_source_choice(user: User, sources: list[SearchSource]) -> SearchSourcesRead:
    return SearchSourcesRead(
        available=[source.name for source in sources], chosen=user.search_sources
    )


def set_source_choice(
    db: Session, user: User, names: list[str] | None, sources: list[SearchSource]
) -> SearchSourcesRead:
    """Save which sources the user's searches ask; None means all of them again."""
    if names is not None:
        available = {source.name for source in sources}
        unknown = [name for name in names if name not in available]
        if unknown:
            raise UnknownSourceError(unknown)
        names = list(dict.fromkeys(names))  # drop repeats, keep the order
    user.search_sources = names
    db.commit()
    return get_source_choice(user, sources)


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
    two sources (same normalized URL) is returned once, from the first source. When the
    form asks for a level, offers more than one level away are left out.
    """
    wanted = query.wanted_level()
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
            if wanted and not fits_level(offer.title, offer.experience_level, wanted):
                continue
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

    results, errors = collect_results(query, chosen_sources(user, sources), limit)

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
