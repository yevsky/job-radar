from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EmploymentType, ExperienceLevel, SourceKind


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
    last_seen_at: datetime | None
    created_at: datetime
