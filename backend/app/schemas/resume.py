from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import ResumeExtracted
from app.schemas.profile import Location, Skill


class ResumeRead(BaseModel):
    """One CV as the list shows it. `extracted` is None if the AI couldn't read it yet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    file_name: str
    created_at: datetime
    extracted: ResumeExtracted | None
    extracted_with: str | None
    applied_to_profile_at: datetime | None


class ResumeDetail(ResumeRead):
    """One CV with the text read from the PDF, so the user can check it."""

    text: str


class ResumeApply(BaseModel):
    """The fields the user ticked to copy into the profile; fields not sent stay as they are.

    Same limits as the profile endpoints. The summary has no place in the profile, so it's
    not here (the frontend may send it; it's ignored).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    desired_position: str | None = Field(default=None, max_length=120)
    experience_level: ExperienceLevel | None = None
    skills: list[Skill] | None = Field(default=None, max_length=50)
    locations: list[Location] | None = Field(default=None, max_length=10)
    employment_types: list[EmploymentType] | None = None
    # 'add': the CV's skills join the profile's (the default). 'replace': the profile keeps
    # only the CV's skills, e.g. when the old list was typed for another kind of job.
    skills_mode: Literal['add', 'replace'] = 'add'
