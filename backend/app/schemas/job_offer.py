from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EmploymentType, ExperienceLevel


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
