from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import EmploymentType, ExperienceLevel

SearchTerm = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]


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
    skills: list[SearchTerm] = Field(default=[], max_length=10)
    location: list[SearchTerm] = Field(default=[], max_length=5)
    employment_types: list[EmploymentType] = []
    remote_only: bool = False
    posted_within: PostedWithin | None = None

    def is_empty(self) -> bool:
        """True if there is nothing to search for: no position and no skills."""
        return not (self.position or '').strip() and not any(s.strip() for s in self.skills)

    def text(self) -> str:
        """The keywords as one phrase, e.g. 'Senior Python dev FastAPI Warsaw OR Remote'.

        Employment types and posted_within are left out: each source sends them as its own
        filters (or adds them to the phrase if it has no such filter).
        """
        words = [self.experience_level or '', self.position or '', *self.skills]
        parts = [word.strip() for word in words if word.strip()]

        locations = [location.strip() for location in self.location if location.strip()]
        if self.remote_only and not any(loc.lower() == 'remote' for loc in locations):
            locations.append('Remote')
        if locations:
            parts.append(' OR '.join(locations))

        return ' '.join(parts)
