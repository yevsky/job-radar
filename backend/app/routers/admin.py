from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.dependencies import DbSession
from app.dependencies import require_role
from app.models import User
from app.models.role import RoleName
from app.schemas.user import UserRead

router = APIRouter(
    prefix='/admin', tags=['admin'], dependencies=[Depends(require_role(RoleName.ADMIN))]
)


@router.get('/users', response_model=list[UserRead])
def get_all_users(db: DbSession) -> Sequence[User]:
    """Return the list of all users."""
    return db.scalars(select(User).order_by(User.id)).all()
