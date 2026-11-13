from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Technology,
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
    lowered = [name.lower() for name in data.skills]
    existing = db.scalars(select(Technology).where(func.lower(Technology.name).in_(lowered))).all()
    by_key = {tech.name.lower(): tech for tech in existing}

    technologies = []
    for name in data.skills:
        tech = by_key.get(name.lower())
        if tech is None:
            tech = Technology(name=name)
        technologies.append(tech)

    user.technologies = technologies
    db.commit()
    db.refresh(user)
    return to_profile_read(user)


def delete_profile(db: Session, user: User) -> None:
    user.profile = None
    user.preferred_locations = []
    user.preferred_employment_types = []
    user.technologies = []
    db.commit()
