"""What the admin dashboard shows: totals and two small time series."""

from datetime import date

from pydantic import BaseModel

from app.models.enums import ApplicationStatus


class DayCount(BaseModel):
    day: date  # a day, or the Monday that starts a week
    count: int


class AdminStats(BaseModel):
    users: int
    admins: int
    new_users_last_7_days: int
    public_offers: int  # shown in everyone's list
    hidden_offers: int  # public, but hidden by an admin
    private_offers: int  # saved from a search or added by one user
    applications: int
    applications_by_status: dict[ApplicationStatus, int]
    searches_today: int
    searches_last_7_days: int
    analyses: int
    conversations: int
    searches_by_day: list[DayCount]  # the last 14 days, oldest first, days without any too
    signups_by_week: list[DayCount]  # the last 8 weeks, oldest first
