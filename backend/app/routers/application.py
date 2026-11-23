from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db.dependencies import DbSession
from app.dependencies import CurrentUser, get_current_user
from app.models.enums import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationStats,
    ApplicationUpdate,
    CalendarEvent,
    StaleStage,
    StatsRange,
    StatusChangeRead,
)
from app.services.application import (
    ApplicationNotFoundError,
    OfferNotFoundError,
    calendar,
    create_application,
    delete_application,
    get_history,
    list_applications,
    stale,
    stats,
    to_read,
    update_application,
)

MAX_CALENDAR_DAYS = 92

router = APIRouter(
    prefix='/applications', tags=['applications'], dependencies=[Depends(get_current_user)]
)

not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Application not found')


@router.get('', response_model=list[ApplicationRead])
def read_applications(
    db: DbSession,
    user: CurrentUser,
    status_: Annotated[ApplicationStatus | None, Query(alias='status')] = None,
) -> list[ApplicationRead]:
    """Your applications (saved offers included), most recently changed first."""
    return [to_read(a) for a in list_applications(db, user.id, status_)]


@router.post('', response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def add_application(
    data: ApplicationCreate, db: DbSession, user: CurrentUser, response: Response
) -> ApplicationRead:
    """Start tracking an offer; if it is already tracked, that application is returned (200)."""
    try:
        application, created = create_application(db, user.id, data)
    except OfferNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found'
        ) from err
    if not created:
        response.status_code = status.HTTP_200_OK
    return to_read(application)


# The fixed paths come before /{application_id}, so FastAPI doesn't try to read 'calendar' as an id.
@router.get('/calendar', response_model=list[CalendarEvent])
def read_calendar(
    db: DbSession,
    user: CurrentUser,
    start: Annotated[date, Query(alias='from')],
    end: Annotated[date, Query(alias='to')],
) -> list[CalendarEvent]:
    """Applied dates, status changes, interviews and deadlines between two days (inclusive)."""
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' must not be after 'to'",
        )
    if end - start > timedelta(days=MAX_CALENDAR_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Ask for at most {MAX_CALENDAR_DAYS} days at a time',
        )
    return calendar(db, user.id, start, end)


@router.get('/stats', response_model=ApplicationStats)
def read_stats(
    db: DbSession, user: CurrentUser, range_: Annotated[StatsRange, Query(alias='range')] = '30d'
) -> ApplicationStats:
    """Dashboard numbers: the funnel, where applications stopped, and weekly activity."""
    return stats(db, user.id, range_)


@router.get('/stale', response_model=list[StaleStage])
def read_stale(db: DbSession, user: CurrentUser) -> list[StaleStage]:
    """Per status: how many applications are in it and which haven't moved for too long."""
    return stale(db, user.id)


@router.patch('/{application_id}', response_model=ApplicationRead)
def edit_application(
    application_id: int, data: ApplicationUpdate, db: DbSession, user: CurrentUser
) -> ApplicationRead:
    """Change the status, notes, dates or CV; a new status is added to the history."""
    try:
        return to_read(update_application(db, user.id, application_id, data))
    except ApplicationNotFoundError as err:
        raise not_found from err


@router.delete('/{application_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_application(application_id: int, db: DbSession, user: CurrentUser) -> None:
    try:
        delete_application(db, user.id, application_id)
    except ApplicationNotFoundError as err:
        raise not_found from err


@router.get('/{application_id}/history', response_model=list[StatusChangeRead])
def read_history(application_id: int, db: DbSession, user: CurrentUser) -> list[StatusChangeRead]:
    """Every status the application had, oldest first."""
    try:
        return get_history(db, user.id, application_id)
    except ApplicationNotFoundError as err:
        raise not_found from err
