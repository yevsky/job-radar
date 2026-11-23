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

from app.models.enums import ApplicationStatus, EmploymentType, ExperienceLevel, SourceKind
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
    found_via: str | None
    url: str
    is_active: bool
    is_private: bool
    description: str | None
    last_seen_at: datetime | None
    created_at: datetime


class MyOfferApplication(BaseModel):
    """Where the user's application for the offer is now."""

    id: int
    status: ApplicationStatus
    updated_at: datetime


class MyOfferItem(JobOfferListItem):
    """One offer on the "My offers" page: one the user added, or one they track."""

    source: SourceKind
    found_via: str | None
    url: str
    is_active: bool
    is_private: bool
    added_at: datetime  # when the user added the offer, or started tracking a public one
    application: MyOfferApplication | None


class AdminJobOfferItem(JobOfferListItem):
    """One public offer in the admin overview, hidden ones included."""

    source: SourceKind
    found_via: str | None
    url: str
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    saved_by: int  # how many users track it (saved or applied)


class AdminJobOfferPage(BaseModel):
    items: list[AdminJobOfferItem]
    total: int
    limit: int
    offset: int


class AdminJobOfferFilters(BaseModel):
    q: str | None = None  # in the title or the company name
    source: SourceKind | None = None
    is_active: bool | None = None  # None = both shown and hidden


class JobOfferStatusUpdate(BaseModel):
    is_active: bool


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
    description: str | None = Field(default=None, max_length=20_000)

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
