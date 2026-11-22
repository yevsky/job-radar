"""The match analysis of one offer against the user: score, reasons and the points behind it."""

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """The points of each rubric part. Every part except role_fit is decided by code."""

    required_skills: int = Field(ge=0, le=45)
    nice_to_have_skills: int = Field(ge=0, le=10)
    experience_level: int = Field(ge=0, le=20)
    location: int = Field(ge=0, le=10)
    employment_type: int = Field(ge=0, le=5)
    role_fit: int = Field(ge=0, le=10)  # the model's 0-10

    @property
    def total(self) -> int:
        parts = (
            self.required_skills,
            self.nice_to_have_skills,
            self.experience_level,
            self.location,
            self.employment_type,
            self.role_fit,
        )
        return max(0, min(100, sum(parts)))


class AnalysisResult(BaseModel):
    """What the "How you match" card shows; issue 11 stores it per offer."""

    score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    summary: str
    reasons: list[str]
    red_flags: list[str]
    matched_skills: list[str]  # the user's skills the posting asks for, in the user's spelling
    missing_skills: list[str]  # required things none of the user's skills covers
    provider: str
    model: str
    prompt_version: str
