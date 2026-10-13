from sqlalchemy.orm import Session

from app.auth.schemas import UserRegister
from app.auth.service import register_user


def test_register_user_creates_user_with_default_role(db: Session) -> None:
    user = register_user(db, UserRegister(email='kot@example.com', password='kot12345'))

    assert user.id is not None
    assert user.email == 'kot@example.com'
    assert user.role.name == 'user'
