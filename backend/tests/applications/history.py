"""Build applications with a known status history, straight in the database."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Application, ApplicationStatusChange, JobOffer
from app.models.enums import ApplicationStatus as S


def track(
    db: Session,
    user_id: int,
    offer: JobOffer,
    steps: list[tuple[S, datetime]],
    interview_at: datetime | None = None,
) -> Application:
    """An application that went through `steps` (status, when), oldest first."""
    applied = next((at for status, at in steps if status != S.SAVED), None)
    application = Application(
        user_id=user_id,
        job_offer=offer,
        status=steps[-1][0],
        applied_at=applied,
        interview_at=interview_at,
        created_at=steps[0][1],
        updated_at=steps[-1][1],
        status_changes=[ApplicationStatusChange(status=s, changed_at=at) for s, at in steps],
    )
    db.add(application)
    db.flush()
    return application
