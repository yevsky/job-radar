from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmploymentType, ExperienceLevel


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    experience_level: ExperienceLevel | None = None
    desired_position: str | None = Field(default=None, max_length=120)


class ProfileRead(BaseModel):
    first_name: str | None
    last_name: str | None
    bio: str | None
    experience_level: ExperienceLevel | None
    desired_position: str | None
    preferred_locations: list[str]
    preferred_employment_types: list[EmploymentType]
    skills: list[str]
