from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.levels import levels_in, remove_levels
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.job_offer import JobOfferImport

MAX_SKILLS = 10
MAX_LOCATIONS = 5

SearchTerm = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
SearchLocation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class PostedWithin(StrEnum):
    DAY = 'day'
    WEEK = 'week'
    MONTH = 'month'


class SearchQuery(BaseModel):
    """The search form: prefilled from the profile, and the user can change every field.

    It is also all a search source receives, so it holds job fields only, never personal data.
    """

    position: str | None = Field(default=None, max_length=120)
    experience_level: ExperienceLevel | None = None
    skills: list[SearchTerm] = Field(default=[], max_length=MAX_SKILLS)
    locations: list[SearchLocation] = Field(default=[], max_length=MAX_LOCATIONS)
    employment_types: list[EmploymentType] = []
    remote_only: bool = False
    posted_within: PostedWithin | None = None

    def is_empty(self) -> bool:
        """True if there is nothing to search for: no position and no skills."""
        return not (self.position or '').strip() and not any(s.strip() for s in self.skills)

    def wanted_level(self) -> ExperienceLevel | None:
        """The level to search for: the form's field, else a level word in the position.

        The field wins: experience_level=junior with position 'Senior dev' searches junior.
        """
        if self.experience_level:
            return self.experience_level
        found = levels_in(self.position or '')
        return found[0] if found else None

    def text(self) -> str:
        """The keywords as one phrase, e.g. 'Senior Python dev FastAPI Warsaw OR Remote'.

        Employment types and posted_within are left out: each source sends them as its own
        filters (or adds them to the phrase if it has no such filter).
        """
        level = self.wanted_level()
        position = remove_levels(self.position or '')  # the level is added once, below
        words = [level or '', position, *self.skills]
        parts = [word.strip() for word in words if word.strip()]

        locations = [location.strip() for location in self.locations if location.strip()]
        if self.remote_only and not any(loc.lower() == 'remote' for loc in locations):
            locations.append('Remote')
        if locations:
            parts.append(' OR '.join(locations))

        return ' '.join(parts)


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
