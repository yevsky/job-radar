from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select

from app.db.dependencies import DbSession
from app.dependencies import AI, SearchSources, require_role
from app.models import User
from app.models.enums import SourceKind
from app.models.role import RoleName
from app.schemas.ai import AIProviderStatus
from app.schemas.job_offer import ImportReport, JobOfferRead, JobOfferStatusUpdate
from app.schemas.search import SearchLimitRead, SearchLimitUpdate, SourceStatus
from app.schemas.user import AdminUserRead
from app.services.job_offer import delete_job_offer, set_job_offer_active
from app.services.job_offer_import import ImportFileError, import_offers, parse_json_rows
from app.services.search import UserNotFoundError, set_search_limit

MAX_IMPORT_BYTES = 1_000_000
MAX_IMPORT_ROWS = 500

router = APIRouter(
    prefix='/admin', tags=['admin'], dependencies=[Depends(require_role(RoleName.ADMIN))]
)


@router.get('/users', response_model=list[AdminUserRead])
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


@router.get('/search-sources', response_model=list[SourceStatus])
def check_search_sources(sources: SearchSources) -> list[SourceStatus]:
    """Show each enabled search source and whether it works (API key valid, API reachable)."""
    return [SourceStatus(name=source.name, ok=source.test()) for source in sources]


@router.get('/ai-provider', response_model=AIProviderStatus)
def check_ai_provider(provider: AI) -> AIProviderStatus:
    """Show which AI provider and model the app uses, and whether it answers."""
    return AIProviderStatus(
        provider=provider.name, model=provider.model, base_url=provider.base_url, ok=provider.test()
    )


@router.put('/users/{user_id}/search-limit', response_model=SearchLimitRead)
def update_search_limit(user_id: int, data: SearchLimitUpdate, db: DbSession) -> SearchLimitRead:
    """Give a user their own daily search limit, or null to use the default again."""
    try:
        return set_search_limit(db, user_id, data.search_daily_limit)
    except UserNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found') from err
