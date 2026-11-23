from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status

from app.db.dependencies import DbSession
from app.dependencies import AI, CurrentAdmin, SearchSources, require_role
from app.models import User
from app.models.enums import SourceKind
from app.models.role import RoleName
from app.schemas.admin import AdminStats
from app.schemas.ai import AIProviderStatus
from app.schemas.job_offer import (
    AdminJobOfferFilters,
    AdminJobOfferPage,
    ImportReport,
    JobOfferRead,
    JobOfferStatusUpdate,
)
from app.schemas.search import SearchLimitRead, SearchLimitUpdate, SourceStatus, SourceSwitchUpdate
from app.schemas.user import AdminUserRead, RoleUpdate
from app.services.admin_stats import get_admin_stats
from app.services.job_offer import delete_job_offer, list_public_offers, set_job_offer_active
from app.services.job_offer_import import ImportFileError, import_offers, parse_rows
from app.services.search import (
    UnknownSourceError,
    UserNotFoundError,
    list_source_switches,
    set_search_limit,
    set_source_enabled,
)
from app.services.user_admin import OwnAccountError, change_role, delete_user, list_users

MAX_IMPORT_BYTES = 1_000_000
MAX_IMPORT_ROWS = 500

router = APIRouter(
    prefix='/admin', tags=['admin'], dependencies=[Depends(require_role(RoleName.ADMIN))]
)


@router.get('/stats', response_model=AdminStats)
def read_admin_stats(db: DbSession) -> AdminStats:
    """Numbers for the admin dashboard: users, offers, applications, searches, AI use."""
    return get_admin_stats(db)


@router.get('/users', response_model=list[AdminUserRead])
def get_all_users(db: DbSession) -> Sequence[User]:
    """Return the list of all users, with their role and own search limit."""
    return list_users(db)


USER_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
OWN_ACCOUNT = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="You can't change your own role or delete your own account",
)


@router.patch('/users/{user_id}/role', response_model=AdminUserRead)
def update_user_role(user_id: int, data: RoleUpdate, db: DbSession, admin: CurrentAdmin) -> User:
    """Make a user an admin, or a normal user again. Not for your own account."""
    try:
        return change_role(db, user_id, data.role, admin)
    except UserNotFoundError as err:
        raise USER_NOT_FOUND from err
    except OwnAccountError as err:
        raise OWN_ACCOUNT from err


@router.delete('/users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_user(user_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    """Delete an account with its profile, private offers, applications, CVs and chats."""
    try:
        delete_user(db, user_id, admin)
    except UserNotFoundError as err:
        raise USER_NOT_FOUND from err
    except OwnAccountError as err:
        raise OWN_ACCOUNT from err


@router.post('/job-offers/import', response_model=ImportReport)
def import_job_offers(file: UploadFile, db: DbSession) -> ImportReport:
    """Import public job offers from an uploaded JSON or CSV file.

    JSON: a list of offer objects. CSV: a header row (title, company_name, url, and any of
    location, experience_level, employment_type, deadline, technologies, description), then
    one offer per line. The report says how many were created, updated, skipped, or invalid.
    """
    content = file.file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail='The file is larger than 1 MB.'
        )

    try:
        rows = parse_rows(file.filename, content)
    except ImportFileError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'The file has more than {MAX_IMPORT_ROWS} offers.',
        )

    return import_offers(db, rows, SourceKind.MANUAL)


@router.get('/job-offers', response_model=AdminJobOfferPage)
def list_imported_offers(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    source: SourceKind | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminJobOfferPage:
    """Every public offer (imported or seeded), hidden ones too, newest first.

    `q` looks in the title and company name; `is_active=false` shows only hidden offers.
    """
    filters = AdminJobOfferFilters(q=q, source=source, is_active=is_active)
    return list_public_offers(db, limit, offset, filters)


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
def read_search_sources(
    db: DbSession, sources: SearchSources, check: bool = False
) -> list[SourceStatus]:
    """Every source the server has (SEARCH_SOURCES) and whether it is switched on.

    `check=true` also asks each source's API whether it works (key valid, API reachable),
    which uses one real request per source.
    """
    return list_source_switches(db, sources, check)


@router.put('/search-sources/{name}', response_model=SourceStatus)
def switch_search_source(
    name: str, data: SourceSwitchUpdate, db: DbSession, admin: CurrentAdmin, sources: SearchSources
) -> SourceStatus:
    """Switch a source on or off for every user at once.

    Users keep their own choice (PUT /search/sources); a switched-off source is just left
    out of their searches until it is on again.
    """
    try:
        return set_source_enabled(db, name, data.enabled, admin, sources)
    except UnknownSourceError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f'No search source named {name}'
        ) from err


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
