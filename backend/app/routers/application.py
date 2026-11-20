from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.db.dependencies import DbSession
from app.dependencies import CurrentUser, get_current_user
from app.models.enums import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    StatusChangeRead,
)
from app.services.application import (
    ApplicationNotFoundError,
    OfferNotFoundError,
    create_application,
    delete_application,
    get_history,
    list_applications,
    to_read,
    update_application,
)

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
