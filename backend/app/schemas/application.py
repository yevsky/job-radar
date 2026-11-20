from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.enums import ApplicationStatus
from app.schemas.job_offer import JobOfferListItem

Notes = str | None


class ApplicationCreate(BaseModel):
    job_offer_id: int
    status: ApplicationStatus = ApplicationStatus.APPLIED
    resume_id: int | None = None
    notes: Notes = Field(default=None, max_length=5000)
    applied_at: datetime | None = None


class ApplicationUpdate(BaseModel):
    """Every field is optional; only the fields sent are changed (null clears a field)."""

    status: ApplicationStatus | None = None
    resume_id: int | None = None
    notes: Notes = Field(default=None, max_length=5000)
    applied_at: datetime | None = None
    interview_at: datetime | None = None


class ApplicationRead(BaseModel):
    id: int
    job_offer: JobOfferListItem
    status: ApplicationStatus
    resume_id: int | None
    notes: str | None
    applied_at: datetime | None
    interview_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StatusChangeRead(BaseModel):
    status: ApplicationStatus
    changed_at: datetime


class SavedJobCreate(BaseModel):
    job_offer_id: int


class SavedJobRead(BaseModel):
    """A saved offer: an application with status `saved`, in the shape the Save button uses."""

    id: int
    job_offer: JobOfferListItem
    created_at: datetime


class CalendarEventKind(StrEnum):
    APPLIED = 'applied'
    STATUS_CHANGE = 'status_change'
    INTERVIEW = 'interview'
    DEADLINE = 'deadline'


class CalendarEvent(BaseModel):
    date: date
    kind: CalendarEventKind
    title: str
    company_name: str
    job_offer_id: int
    application_id: int | None
    status: ApplicationStatus | None
    time: str | None  # 'HH:MM' (UTC), interviews only
