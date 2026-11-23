from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.role import RoleName


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role_id: int
    # The role's name ('user' or 'admin'), so the frontend doesn't have to guess from role_id
    role: RoleName
    created_at: datetime

    @field_validator('role', mode='before')
    @classmethod
    def role_name(cls, role: Any) -> Any:  # noqa: ANN401 - a Role row or already a name
        """The model has a Role object here; the API shows only its name."""
        return getattr(role, 'name', role)


class AdminUserRead(UserRead):
    """What admins see in the user list: also the user's own daily search limit."""

    search_daily_limit: int | None  # None means the default from settings


class RoleUpdate(BaseModel):
    """Body of PATCH /admin/users/{id}/role."""

    role: RoleName


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'
