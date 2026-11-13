from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.enums import EmploymentType, ExperienceLevel

Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


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


class LocationsUpdate(BaseModel):
    locations: list[Location] = Field(max_length=10)

    @field_validator('locations')
    @classmethod
    def remove_duplicates(cls, locations: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for location in locations:
            key = location.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(location)
        return result
