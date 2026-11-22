"""What the AI model must answer for each task. Validated by app/ai/structured.generate."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, UrlConstraints, field_validator

from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.job_offer import TechnologyName
from app.schemas.profile import unique_ignoring_case

# The longest posting text a user can paste: the same as an offer's description
MAX_POSTING_TEXT = 20_000


class AIAnswer(BaseModel):
    """Base for model answers: trims strings, ignores fields we didn't ask for."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='ignore')


def known_or_none[E: StrEnum](value: object, enum: type[E]) -> E | None:
    """The enum member a model's word stands for, or None if we don't have it.

    'B2B' -> b2b, 'Full-time' -> full_time, 'expert' -> None.
    """
    if isinstance(value, enum):
        return value
    if not isinstance(value, str):
        return None
    word = value.strip().lower().replace('-', '_').replace(' ', '_')
    return next((member for member in enum if member.value == word), None)


class ParsedOffer(AIAnswer):
    """The fields of one job posting, read from its text.

    Lenient where a small model is often wrong: an unknown level, employment type or date
    becomes None and an odd technology is dropped, instead of failing the whole answer.
    """

    title: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=100)
    experience_level: ExperienceLevel | None = None
    employment_type: EmploymentType | None = None
    deadline: date | None = None
    technologies: list[TechnologyName] = Field(default=[], max_length=30)

    @field_validator('experience_level', mode='before')
    @classmethod
    def known_level(cls, value: object) -> ExperienceLevel | None:
        return known_or_none(value, ExperienceLevel)

    @field_validator('employment_type', mode='before')
    @classmethod
    def known_employment_type(cls, value: object) -> EmploymentType | None:
        return known_or_none(value, EmploymentType)

    @field_validator('deadline', mode='before')
    @classmethod
    def date_or_none(cls, value: object) -> date | None:
        """'2026-12-15' or '2026-12-15T23:59' -> a date; 'ASAP', 'not given' -> None."""
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            return None
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None

    @field_validator('technologies', mode='before')
    @classmethod
    def drop_odd_names(cls, names: object) -> object:
        """Drop names that aren't text, are empty or are too long to be one technology."""
        if not isinstance(names, list):
            return names
        return [n for n in names if isinstance(n, str) and 0 < len(n.strip()) <= 50]

    @field_validator('technologies')
    @classmethod
    def remove_duplicates(cls, names: list[str]) -> list[str]:
        return unique_ignoring_case(names)


def clean_names(names: object, max_chars: int, max_items: int) -> object:
    """Trimmed text items, without blanks, too long ones and repeats, cut to max_items.

    Anything that isn't a list is returned as it is, so Pydantic reports it.
    """
    if not isinstance(names, list):
        return names
    kept = [n.strip() for n in names if isinstance(n, str) and 0 < len(n.strip()) <= max_chars]
    return unique_ignoring_case(kept)[:max_items]


def cut_text(value: object, max_chars: int) -> object:
    """A trimmed string cut to max_chars ('' becomes None); anything else as it is."""
    if not isinstance(value, str):
        return value
    return value.strip()[:max_chars] or None


class ResumeExtracted(AIAnswer):
    """What a CV says about the person's job wishes and skills.

    Lenient everywhere: a CV is long and every field is optional, so a value that doesn't fit
    is dropped or cut instead of failing the whole answer. Limits are the profile's.
    """

    desired_position: str | None = Field(default=None, max_length=120)
    experience_level: ExperienceLevel | None = None
    skills: list[str] = Field(default=[], max_length=50)
    locations: list[str] = Field(default=[], max_length=10)
    employment_types: list[EmploymentType] = []
    summary: str | None = Field(default=None, max_length=500)

    @field_validator('desired_position', mode='before')
    @classmethod
    def cut_position(cls, value: object) -> object:
        return cut_text(value, 120)

    @field_validator('summary', mode='before')
    @classmethod
    def cut_summary(cls, value: object) -> object:
        return cut_text(value, 500)

    @field_validator('experience_level', mode='before')
    @classmethod
    def known_level(cls, value: object) -> ExperienceLevel | None:
        return known_or_none(value, ExperienceLevel)

    @field_validator('skills', mode='before')
    @classmethod
    def clean_skills(cls, names: object) -> object:
        return clean_names(names, max_chars=50, max_items=50)

    @field_validator('locations', mode='before')
    @classmethod
    def clean_locations(cls, names: object) -> object:
        return clean_names(names, max_chars=100, max_items=10)

    @field_validator('employment_types', mode='before')
    @classmethod
    def known_employment_types(cls, values: object) -> object:
        """['B2B', 'freelance', 'b2b'] -> [b2b]: unknown ones and repeats dropped."""
        if not isinstance(values, list):
            return values
        known = [known_or_none(value, EmploymentType) for value in values]
        return list(dict.fromkeys(value for value in known if value is not None))


class Requirement(AIAnswer):
    """One requirement of a posting and which of the candidate's skills covers it."""

    text: str = Field(min_length=1, max_length=200)
    required: bool  # False for "nice to have"
    skill: str | None = Field(default=None, max_length=50)  # one of the candidate's skills, or None


class OfferAnalysisOutput(AIAnswer):
    """The model's part of a match analysis. Code decides matched skills and the score."""

    requirements: list[Requirement] = Field(default=[], max_length=30)
    role_fit: int = Field(ge=0, le=10)
    summary: str = Field(max_length=300)
    reasons: list[str] = Field(default=[], max_length=5)
    red_flags: list[str] = Field(default=[], max_length=5)


class AIProviderStatus(BaseModel):
    """Which AI provider the app uses and whether it answers."""

    provider: str
    model: str
    base_url: str | None
    ok: bool


class JobOfferParseRequest(BaseModel):
    """A posting pasted by the user, and its link if they have one."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=50, max_length=MAX_POSTING_TEXT)
    url: Annotated[HttpUrl, UrlConstraints(max_length=2048)] | None = None


class JobOfferParseResponse(ParsedOffer):
    """A draft offer to check and correct, then save with POST /job-offers. Nothing is saved.

    The description is the pasted text; parsed_with names the provider and model, e.g.
    'ollama/qwen2.5:3b'.
    """

    url: str | None
    description: str
    parsed_with: str
