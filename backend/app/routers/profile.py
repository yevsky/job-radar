from fastapi import APIRouter

from app.db.dependencies import DbSession
from app.dependencies import CurrentUser
from app.schemas.profile import (
    EmploymentTypesUpdate,
    LocationsUpdate,
    ProfileRead,
    ProfileUpdate,
    SkillsUpdate,
)
from app.services.profile import (
    get_profile,
    set_employment_types,
    set_locations,
    set_skills,
    upsert_profile,
)

router = APIRouter(prefix='/profile', tags=['profile'])


@router.get('/me', response_model=ProfileRead)
def read_my_profile(user: CurrentUser) -> ProfileRead:
    return get_profile(user)


@router.put('/me', response_model=ProfileRead)
def update_my_profile(data: ProfileUpdate, user: CurrentUser, db: DbSession) -> ProfileRead:
    return upsert_profile(db, user, data)


@router.put('/me/locations', response_model=ProfileRead)
def update_my_location(data: LocationsUpdate, user: CurrentUser, db: DbSession) -> ProfileRead:
    return set_locations(db, user, data)


@router.put('/me/employment-types', response_model=ProfileRead)
def update_my_employment_types(
    data: EmploymentTypesUpdate, user: CurrentUser, db: DbSession
) -> ProfileRead:
    return set_employment_types(db, user, data)


@router.put('/me/skills', response_model=ProfileRead)
def update_my_skills(data: SkillsUpdate, user: CurrentUser, db: DbSession) -> ProfileRead:
    return set_skills(db, user, data)
