from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.config import settings
from app.core.levels import levels_in
from app.models.enums import ExperienceLevel
from app.schemas.job_offer import JobOfferImport

MAX_LOCATIONS = 5
MAX_PAGE = 10

SearchLocation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
CountryCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r'^[a-zA-Z]{2}$')
]


class PostedWithin(StrEnum):
    DAY = 'day'
    WEEK = 'week'
    MONTH = 'month'


class SourceFeature(StrEnum):
    """Form fields a source can use. Position and cities go into the phrase, so every
    source uses them; the frontend greys out a field none of the chosen sources uses."""

    COUNTRY = 'country'
    POSTED_WITHIN = 'posted_within'
    PAGES = 'pages'


class SearchQuery(BaseModel):
    """The search form: prefilled from the profile, and the user can change every field.

    It is also all a search source receives, so it holds job fields only, never personal data.
    The level is part of the position ('Junior Python developer'), the way job boards and
    Google Jobs expect it: JSearch's own level filter finds almost nothing outside the US.
    """

    position: str | None = Field(default=None, max_length=120)
    locations: list[SearchLocation] = Field(default=[], max_length=MAX_LOCATIONS)
    country: CountryCode = Field(default_factory=lambda: settings.jsearch_country)
    posted_within: PostedWithin | None = None
    page: int = Field(default=1, ge=1, le=MAX_PAGE)

    def is_empty(self) -> bool:
        """True if there is nothing to search for: no position."""
        return not (self.position or '').strip()

    def wanted_level(self) -> ExperienceLevel | None:
        """The level named in the position: 'Junior Python developer' -> junior."""
        found = levels_in(self.position or '')
        return found[0] if found else None

    def cities(self) -> list[str]:
        return [location.strip() for location in self.locations if location.strip()]

    def text(self) -> str:
        """The keywords as one phrase, e.g. 'Junior Python developer Warsaw OR Remote'.

        Country, posted_within and page are left out: each source sends them as its own
        filters, or doesn't use them.
        """
        parts = [(self.position or '').strip()]
        if self.cities():
            parts.append(' OR '.join(self.cities()))
        return ' '.join(part for part in parts if part)


class SearchResult(JobOfferImport):
    """One offer found by a search, with the name of the source that found it."""

    found_via: str = Field(min_length=1, max_length=50)


class SourceError(BaseModel):
    """A source that failed during a search; the other sources' results are still returned."""

    source: str
    message: str


class SearchResponse(BaseModel):
    query: str  # the phrase that was sent, so the user sees exactly what left the server
    results: list[SearchResult]
    errors: list[SourceError]
    searches_left_today: int
    page: int
    has_more: bool  # True if a source may have another page ("Next" in the frontend)
    hidden: int = 0  # results left out: list pages, other cities, levels far from the position


class SourceStatus(BaseModel):
    name: str
    ok: bool


class SearchUsage(BaseModel):
    """How many searches the user may run today, and how many are left."""

    daily_limit: int
    used_today: int
    left_today: int


class SearchLimitUpdate(BaseModel):
    """Body of the admin endpoint; None goes back to the default from settings."""

    search_daily_limit: int | None = Field(ge=0, le=1000)


class SearchLimitRead(BaseModel):
    user_id: int
    search_daily_limit: int | None  # the user's own limit, or None
    effective_limit: int  # what actually applies: the user's limit or the default


SourceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class SearchSourcesRead(BaseModel):
    available: list[str]  # the sources the app has turned on, in the order they're asked
    chosen: list[str] | None  # the user's choice; None means all available ones
    # which form fields each source uses, e.g. {'jsearch': ['country', 'posted_within', ...]}
    features: dict[str, list[SourceFeature]] = {}


class SearchSourcesUpdate(BaseModel):
    # None goes back to all sources; otherwise at least one name
    sources: list[SourceName] | None = Field(default=None, min_length=1)
