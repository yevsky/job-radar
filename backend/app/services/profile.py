from sqlalchemy.orm import Session

from app.models import (
    User,
    UserPreferredEmploymentType,
    UserPreferredLocation,
    UserProfile,
)
from app.schemas.profile import (
    EmploymentTypesUpdate,
    LocationsUpdate,
    ProfileRead,
    ProfileUpdate,
    SkillsUpdate,
)
from app.services.technology import get_or_create_technologies


def to_profile_read(user: User) -> ProfileRead:
    profile = user.profile
    return ProfileRead(
        experience_level=profile.experience_level if profile else None,
        desired_position=profile.desired_position if profile else None,
        preferred_employment_types=[e.employment_type for e in user.preferred_employment_types],
        preferred_locations=[p.location for p in user.preferred_locations],
        skills=[t.name for t in user.technologies],
    )


def get_profile(user: User) -> ProfileRead:
    return to_profile_read(user)


def upsert_profile(db: Session, user: User, data: ProfileUpdate) -> ProfileRead:
    if user.profile is None:
        user.profile = UserProfile()

    for field, value in data.model_dump().items():
        setattr(user.profile, field, value)

    db.commit()
    db.refresh(user)

    return to_profile_read(user)


def set_locations(db: Session, user: User, data: LocationsUpdate) -> ProfileRead:
    user.preferred_locations = [UserPreferredLocation(location=loc) for loc in data.locations]
    db.commit()
    db.refresh(user)
    return to_profile_read(user)


def set_employment_types(db: Session, user: User, data: EmploymentTypesUpdate) -> ProfileRead:
    user.preferred_employment_types = [
        UserPreferredEmploymentType(employment_type=t) for t in data.employment_types
    ]
    db.commit()
    db.refresh(user)
    return to_profile_read(user)


def set_skills(db: Session, user: User, data: SkillsUpdate) -> ProfileRead:
    user.technologies = get_or_create_technologies(db, data.skills)
    db.commit()
    db.refresh(user)
    return to_profile_read(user)


def delete_profile(db: Session, user: User) -> None:
    user.profile = None
    user.preferred_locations = []
    user.preferred_employment_types = []
    user.technologies = []
    db.commit()
