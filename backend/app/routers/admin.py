from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select

from app.db.dependencies import DbSession
from app.dependencies import require_role
from app.models import User
from app.models.enums import SourceKind
from app.models.role import RoleName
from app.schemas.job_offer import ImportReport, JobOfferRead, JobOfferStatusUpdate
from app.schemas.user import UserRead
from app.services.job_offer import delete_job_offer, set_job_offer_active
from app.services.job_offer_import import ImportFileError, import_offers, parse_json_rows

MAX_IMPORT_BYTES = 1_000_000
MAX_IMPORT_ROWS = 500

router = APIRouter(
    prefix='/admin', tags=['admin'], dependencies=[Depends(require_role(RoleName.ADMIN))]
)


@router.get('/users', response_model=list[UserRead])
def get_all_users(db: DbSession) -> Sequence[User]:
    """Return the list of all users."""
    return db.scalars(select(User).order_by(User.id)).all()


@router.post('/job-offers/import', response_model=ImportReport)
def import_job_offers(file: UploadFile, db: DbSession) -> ImportReport:
    """Import job offers from an uploaded JSON file (a list of offer objects)."""
    content = file.file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail='The file is larger than 1 MB.'
        )

    try:
        rows = parse_json_rows(content)
    except ImportFileError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'The file has more than {MAX_IMPORT_ROWS} offers.',
        )

    return import_offers(db, rows, SourceKind.MANUAL)


@router.patch('/job-offers/{offer_id}', response_model=JobOfferRead)
def update_job_offer_status(
    offer_id: int, data: JobOfferStatusUpdate, db: DbSession
) -> JobOfferRead:
    """Hide an offer from the list (is_active=false) or show it again."""
    offer = set_job_offer_active(db, offer_id, data.is_active)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found')
    return offer


@router.delete('/job-offers/{offer_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_job_offer(offer_id: int, db: DbSession) -> None:
    """Delete an offer for good."""
    if not delete_job_offer(db, offer_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job offer not found')
