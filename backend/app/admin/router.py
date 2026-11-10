from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth.dependencies import require_role
from app.auth.schemas import UserRead
from app.db.dependencies import DbSession
from app.models import User
from app.models.role import RoleName

router = APIRouter(
    prefix='/admin', tags=['admin'], dependencies=[Depends(require_role(RoleName.ADMIN))]
)


@router.get('/users', response_model=list[UserRead])
def get_all_users(db: DbSession) -> Sequence[User]:
    """Return the list of all users."""
    return db.scalars(select(User).order_by(User.id)).all()
