from sqlalchemy import LargeBinary, func, select
from sqlalchemy.orm import Session

from app.models import (
    Resume,
    Role,
    Technology,
    User,
    UserPreferredEmploymentType,
    UserPreferredLocation,
    UserProfile,
)
from app.models.enums import EmploymentType, ExperienceLevel
from app.models.role import RoleName
from app.models.technology import user_technologies
from tests.helpers import USER_EMAIL


def count(db: Session, model: object) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0  # type: ignore[arg-type]


def test_deleting_user_deletes_profile_and_preferences_but_keeps_technologies(
    db: Session,
) -> None:
    role = db.scalar(select(Role).where(Role.name == RoleName.USER))
    assert role is not None
    python = Technology(name='Python')
    user = User(
        email=USER_EMAIL,
        hashed_password='not-a-real-hash',
        role=role,
        profile=UserProfile(
            desired_position='Backend developer', experience_level=ExperienceLevel.JUNIOR
        ),
        preferred_locations=[UserPreferredLocation(location='Remote')],
        preferred_employment_types=[
            UserPreferredEmploymentType(employment_type=EmploymentType.B2B)
        ],
        technologies=[python],
    )
    db.add(user)
    db.flush()
    assert count(db, UserProfile) == 1
    assert count(db, user_technologies) == 1

    db.delete(user)
    db.flush()

    assert count(db, UserProfile) == 0
    assert count(db, UserPreferredLocation) == 0
    assert count(db, UserPreferredEmploymentType) == 0
    assert count(db, user_technologies) == 0
    assert db.scalar(select(Technology).where(Technology.name == 'Python')) is not None


def test_deleting_user_deletes_their_resumes(db: Session) -> None:
    role = db.scalar(select(Role).where(Role.name == RoleName.USER))
    assert role is not None
    user = User(email=USER_EMAIL, hashed_password='not-a-real-hash', role=role)
    db.add(user)
    db.flush()
    db.add(Resume(user_id=user.id, label='Backend CV', file_name='cv.pdf', text='Python'))
    db.flush()
    assert count(db, Resume) == 1

    db.delete(user)
    db.flush()

    assert count(db, Resume) == 0


def test_no_resume_column_holds_file_bytes() -> None:
    """We keep the CV's text, never the PDF itself."""
    types = [type(column.type) for column in Resume.__table__.columns]
    assert LargeBinary not in types
    assert not any(issubclass(t, LargeBinary) for t in types)
