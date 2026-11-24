from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.db.dependencies import DbSession
from app.dependencies import CurrentUser, get_current_user
from app.schemas.application import SavedJobCreate, SavedJobRead
from app.services.application import (
    NotSavedError,
    OfferNotFoundError,
    list_saved,
    save_offer,
    unsave_offer,
)

router = APIRouter(
    prefix='/saved-jobs', tags=['saved-jobs'], dependencies=[Depends(get_current_user)]
)


@router.get('', response_model=list[SavedJobRead])
def read_saved_jobs(db: DbSession, user: CurrentUser) -> list[SavedJobRead]:
    """Offers you saved and haven't applied to yet, newest first."""
    return list_saved(db, user.id)


@router.post('', response_model=SavedJobRead, status_code=status.HTTP_201_CREATED)
def save_job(
    data: SavedJobCreate, db: DbSession, user: CurrentUser, response: Response
) -> SavedJobRead:
    """Save an offer for later; an offer you already track is returned as is (200)."""
    try:
        saved, created = save_offer(db, user.id, data.job_offer_id)
    except OfferNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found'
        ) from err
    if not created:
        response.status_code = status.HTTP_200_OK
    return saved


@router.delete('/{job_offer_id}', status_code=status.HTTP_204_NO_CONTENT)
def unsave_job(job_offer_id: int, db: DbSession, user: CurrentUser) -> None:
    """Remove a saved offer (by the offer's id). Offers you already applied to stay.

    An offer only you can see (one you added or kept from a search) is deleted with its
    analyses and summary; a job board offer stays on the board.
    """
    try:
        unsave_offer(db, user.id, job_offer_id)
    except NotSavedError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='This offer is not saved'
        ) from err
