from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import ApplicationStatus
from app.schemas.job_offer import JobOfferListItem

# The stages an application moves through, in order. `saved` comes before the funnel, and
# `rejected` / `declined` are outcomes rather than stages.
FUNNEL_STAGES: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.APPLIED,
    ApplicationStatus.SCREENING,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
    ApplicationStatus.ACCEPTED,
)

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


StatsRange = Literal['30d', '90d', 'all']


class FunnelStep(BaseModel):
    stage: ApplicationStatus
    reached: int  # applications that got at least this far


class Outcome(BaseModel):
    stage: ApplicationStatus  # the furthest stage the application reached
    status: ApplicationStatus  # where it is now
    count: int


class WeeklyCount(BaseModel):
    week_start: date  # Monday
    saved: int
    applied: int
    replied: int  # applications whose first reply from the company came this week


class ApplicationStats(BaseModel):
    range: StatsRange
    funnel: list[FunnelStep]
    outcomes: list[Outcome]
    weekly: list[WeeklyCount]
    replied: int  # applications sent in the range that got any reply (good or bad)


class StaleItem(BaseModel):
    application_id: int
    job_offer_id: int
    title: str
    company_name: str
    since: datetime  # when it entered its current status (for interviews: the interview)
    days: int  # whole days since then


class StaleStage(BaseModel):
    """Applications in one status that haven't moved for longer than that status allows."""

    stage: ApplicationStatus
    after_days: int  # the rule: stale after this many days without a change
    total: int  # all applications in this status right now
    items: list[StaleItem]  # the stale ones, longest wait first
