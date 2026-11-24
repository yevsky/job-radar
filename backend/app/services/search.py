from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.levels import fits_level, levels_in
from app.core.locations import location_fits
from app.models import SearchRun, SearchSourceSwitch, User
from app.models.enums import ExperienceLevel
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import (
    MAX_LOCATIONS,
    HiddenReason,
    HiddenResult,
    SearchLimitRead,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchSourcesRead,
    SearchUsage,
    SourceError,
    SourceStatus,
)
from app.search_sources.base import SearchSource, SearchSourceError
from app.services.job_offer_import import normalize_url


class EmptyQueryError(Exception):
    """The search form has no position, so there is nothing to search for."""


class SearchLimitError(Exception):
    """The user has used all of today's searches."""


class UserNotFoundError(Exception):
    """No user with this id."""


class UnknownSourceError(Exception):
    """A source name the app doesn't have, or one an admin switched off."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(names)
        self.names = names


class NoSourcesError(Exception):
    """An admin switched off every search source, so there is nothing to ask."""


def switched_off(db: Session) -> set[str]:
    """Names of the sources an admin switched off for everyone."""
    return set(
        db.scalars(select(SearchSourceSwitch.name).where(SearchSourceSwitch.is_enabled.is_(False)))
    )


def enabled_sources(db: Session, sources: list[SearchSource]) -> list[SearchSource]:
    """The server's sources (SEARCH_SOURCES) minus the ones an admin switched off."""
    off = switched_off(db)
    return [source for source in sources if source.name not in off]


def list_source_switches(
    db: Session, sources: list[SearchSource], check: bool = False
) -> list[SourceStatus]:
    """Every source the server has, with its switch; `check` also calls each one's API."""
    switches = {row.name: row for row in db.scalars(select(SearchSourceSwitch))}
    result = []
    for source in sources:
        switch = switches.get(source.name)
        result.append(
            SourceStatus(
                name=source.name,
                enabled=switch.is_enabled if switch else True,
                ok=source.test() if check else None,
                features=sorted(source.features),
                updated_at=switch.updated_at if switch else None,
            )
        )
    return result


def set_source_enabled(
    db: Session, name: str, enabled: bool, admin: User, sources: list[SearchSource]
) -> SourceStatus:
    """Switch a source on or off for every user. Users' own choices are kept as they are."""
    if name not in {source.name for source in sources}:
        raise UnknownSourceError([name])
    switch = db.get(SearchSourceSwitch, name)
    if switch is None:
        switch = SearchSourceSwitch(name=name, is_enabled=enabled)
        db.add(switch)
    switch.is_enabled = enabled
    switch.updated_by_id = admin.id
    db.commit()
    return next(s for s in list_source_switches(db, sources) if s.name == name)


def chosen_sources(user: User, sources: list[SearchSource]) -> list[SearchSource]:
    """The enabled sources the user chose, in the app's order; all of them if none is left."""
    if not user.search_sources:
        return sources
    chosen = [source for source in sources if source.name in user.search_sources]
    return chosen or sources  # an admin may have turned off every source the user chose


def get_source_choice(
    user: User, sources: list[SearchSource], turned_off: list[str] | None = None
) -> SearchSourcesRead:
    """`sources` are the ones switched on; `turned_off` the ones an admin switched off."""
    return SearchSourcesRead(
        available=[source.name for source in sources],
        chosen=user.search_sources,
        features={source.name: sorted(source.features) for source in sources},
        turned_off=turned_off or [],
    )


def set_source_choice(
    db: Session, user: User, names: list[str] | None, sources: list[SearchSource]
) -> SearchSourcesRead:
    """Save which sources the user's searches ask; None means all of them again.

    `sources` are the ones switched on, so a switched-off source can't be chosen.
    """
    if names is not None:
        available = {source.name for source in sources}
        unknown = [name for name in names if name not in available]
        if unknown:
            raise UnknownSourceError(unknown)
        names = list(dict.fromkeys(names))  # drop repeats, keep the order
    user.search_sources = names
    db.commit()
    return get_source_choice(user, sources)


# How a level is written in front of a position: 'Junior Python developer'
LEVEL_WORD = {
    ExperienceLevel.TRAINEE: 'Intern',
    ExperienceLevel.JUNIOR: 'Junior',
    ExperienceLevel.MIDDLE: 'Mid',
    ExperienceLevel.SENIOR: 'Senior',
    ExperienceLevel.LEAD: 'Lead',
}


def position_with_level(position: str | None, level: ExperienceLevel | None) -> str | None:
    """The profile's position with its level in front, unless the position names one.

    ('Python developer', junior) -> 'Junior Python developer'; ('Senior dev', junior) stays.
    The first letter is made a capital either way: 'junior Python dev' -> 'Junior Python dev'.
    """
    if not position or not position.strip():
        return None
    position = position.strip()
    position = position[0].upper() + position[1:]
    if level is None or levels_in(position):
        return position
    return f'{LEVEL_WORD[level]} {position}'[:120]


def default_search_query(user: User) -> SearchQuery:
    """The search form prefilled from the profile: job fields only, never the email."""
    profile = user.profile
    return SearchQuery(
        position=position_with_level(
            profile.desired_position if profile else None,
            profile.experience_level if profile else None,
        ),
        locations=[preferred.location for preferred in user.preferred_locations][:MAX_LOCATIONS],
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


@dataclass
class Collected:
    """What all sources found for one page of a search."""

    results: list[SearchResult] = field(default_factory=list)
    hidden: list[HiddenResult] = field(default_factory=list)
    errors: list[SourceError] = field(default_factory=list)
    has_more: bool = False  # True if any source may have another page
    unreadable: int = 0  # rows a source couldn't read: hidden, but nothing to show

    @property
    def hidden_count(self) -> int:
        return len(self.hidden) + self.unreadable


def hidden_reason(
    offer: JobOfferImport, wanted: ExperienceLevel | None, cities: list[str]
) -> HiddenReason | None:
    """Why our own filters leave this offer out, or None if it stays."""
    if not location_fits(offer.location, cities):
        return HiddenReason.OTHER_CITY
    if wanted and not fits_level(offer.title, offer.experience_level, wanted):
        return HiddenReason.OTHER_LEVEL
    return None


def collect_results(query: SearchQuery, sources: list[SearchSource], limit: int) -> Collected:
    """Ask every source for the query's page and merge the answers.

    A source that fails is listed in errors and the others still count. A link found by
    two sources (same normalized URL) is returned once, from the first source. Offers more
    than one level away from a level in the position, or in a city the user didn't ask for,
    go to `hidden` with the reason, next to what the sources left out themselves (Tavily's
    list pages, closed and expired offers).
    """
    wanted = query.wanted_level()
    cities = query.cities()
    found = Collected()
    seen_urls: set[str] = set()

    for source in sources:
        try:
            page = source.search(query, limit)
        except SearchSourceError as err:
            found.errors.append(SourceError(source=source.name, message=str(err)))
            continue
        found.has_more = found.has_more or page.has_more
        found.unreadable += page.skipped

        candidates = [(offer, hidden_reason(offer, wanted, cities)) for offer in page.offers]
        candidates += [(hidden.offer, hidden.reason) for hidden in page.hidden]
        for offer, reason in candidates:
            url = normalize_url(str(offer.url))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            data = offer.model_dump()
            if reason is None:
                found.results.append(SearchResult(**data, found_via=source.name))
            else:
                found.hidden.append(
                    HiddenResult(**data, found_via=source.name, hidden_because=reason)
                )

    return found


def run_search(
    db: Session, user: User, query: SearchQuery, sources: list[SearchSource], limit: int
) -> SearchResponse:
    """Run one search for the user, within their daily limit. Results are not saved.

    Only page 1 counts as a search: a small SearchRun row (who, when, how many results) is
    stored for it. Next pages of the same form are free, up to MAX_PAGE.
    """
    if query.is_empty():
        raise EmptyQueryError

    if not sources:
        raise NoSourcesError  # every source is switched off; checked before the limit

    usage = get_usage(db, user)
    first_page = query.page == 1
    if first_page and usage.left_today == 0:
        raise SearchLimitError  # checked before any source is called, so it costs nothing

    found = collect_results(query, chosen_sources(user, sources), limit)

    left = usage.left_today
    if first_page:
        db.add(SearchRun(user_id=user.id, result_count=len(found.results)))
        db.commit()
        left -= 1

    return SearchResponse(
        query=query.text(),
        results=found.results,
        errors=found.errors,
        searches_left_today=left,
        page=query.page,
        has_more=found.has_more,
        hidden=found.hidden_count,
        hidden_results=found.hidden,
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
