from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    UrlConstraints,
    field_validator,
)

from app.models.enums import EmploymentType, ExperienceLevel, SourceKind
from app.schemas.profile import unique_ignoring_case

TechnologyName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class JobOfferListItem(BaseModel):
    id: int
    title: str
    company_name: str
    location: str | None
    employment_type: EmploymentType | None
    experience_level: ExperienceLevel | None
    deadline: datetime | None
    technologies: list[str]


class JobOfferPage(BaseModel):
    items: list[JobOfferListItem]
    total: int
    limit: int
    offset: int


class JobOfferRead(JobOfferListItem):
    source: SourceKind
    url: str
    is_active: bool
    is_private: bool
    last_seen_at: datetime | None
    created_at: datetime


class JobOfferFilters(BaseModel):
    technologies: list[str] = []
    location: str | None = None
    experience_levels: list[ExperienceLevel] = []
    employment_types: list[EmploymentType] = []


class JobOfferImport(BaseModel):
    """One offer as it arrives from an import/search"""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    url: Annotated[HttpUrl, UrlConstraints(max_length=2048)]
    location: str | None = Field(default=None, max_length=100)
    experience_level: ExperienceLevel | None = None
    employment_type: EmploymentType | None = None
    deadline: datetime | None = None
    technologies: list[TechnologyName] = []

    @field_validator('technologies', mode='before')
    @classmethod
    def drop_blank_names(cls, names: object) -> object:
        if isinstance(names, list):
            return [n for n in names if not (isinstance(n, str) and not n.strip())]
        return names

    @field_validator('technologies')
    @classmethod
    def remove_duplicates(cls, names: list[str]) -> list[str]:
        return unique_ignoring_case(names)


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportReport(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[ImportRowError] = []
