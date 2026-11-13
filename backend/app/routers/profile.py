from fastapi import APIRouter

from app.db.dependencies import DbSession
from app.dependencies import CurrentUser
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.services.profile import get_profile, upsert_profile

router = APIRouter(prefix='/profile', tags=['profile'])


@router.get('/me', response_model=ProfileRead)
def read_my_profile(user: CurrentUser) -> ProfileRead:
    return get_profile(user)


@router.put('/me', response_model=ProfileRead)
def update_my_profile(data: ProfileUpdate, user: CurrentUser, db: DbSession) -> ProfileRead:
    return upsert_profile(db, user, data)
