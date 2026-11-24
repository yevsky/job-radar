from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.enums import EmploymentType, ExperienceLevel

Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Skill = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


def unique_ignoring_case(values: list[str]) -> list[str]:
    """Drop case-insensitive duplicates, keeping the first spelling."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    experience_level: ExperienceLevel | None = None
    desired_position: str | None = Field(default=None, max_length=120)


class ProfileRead(BaseModel):
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
        return unique_ignoring_case(locations)


class EmploymentTypesUpdate(BaseModel):
    employment_types: list[EmploymentType]

    @field_validator('employment_types')
    @classmethod
    def remove_duplicates(cls, employment_types: list[EmploymentType]) -> list[EmploymentType]:
        return list(dict.fromkeys(employment_types))


class SkillsUpdate(BaseModel):
    skills: list[Skill] = Field(max_length=50)

    @field_validator('skills')
    @classmethod
    def remove_duplicates(cls, skills: list[str]) -> list[str]:
        return unique_ignoring_case(skills)
