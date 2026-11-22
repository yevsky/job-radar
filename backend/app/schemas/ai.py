"""What the AI model must answer for each task. Validated by app/ai/structured.generate."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmploymentType, ExperienceLevel


class AIAnswer(BaseModel):
    """Base for model answers: trims strings, ignores fields we didn't ask for."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='ignore')


class ParsedOffer(AIAnswer):
    """The fields of one job posting, read from its text."""

    title: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=100)
    experience_level: ExperienceLevel | None = None
    employment_type: EmploymentType | None = None
    deadline: date | None = None
    technologies: list[str] = Field(default=[], max_length=30)


class ResumeExtracted(AIAnswer):
    """What a CV says about the person's job wishes and skills."""

    desired_position: str | None = Field(default=None, max_length=120)
    experience_level: ExperienceLevel | None = None
    skills: list[str] = Field(default=[], max_length=50)
    locations: list[str] = Field(default=[], max_length=10)
    employment_types: list[EmploymentType] = []
    summary: str | None = Field(default=None, max_length=500)


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
