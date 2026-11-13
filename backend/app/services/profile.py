from sqlalchemy.orm import Session

from app.models import User, UserProfile
from app.schemas.profile import ProfileRead, ProfileUpdate


def to_profile_read(user: User) -> ProfileRead:
    profile = user.profile
    return ProfileRead(
        first_name=profile.first_name if profile else None,
        last_name=profile.last_name if profile else None,
        bio=profile.bio if profile else None,
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
