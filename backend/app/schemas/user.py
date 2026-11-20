from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role_id: int
    created_at: datetime


class AdminUserRead(UserRead):
    """What admins see in the user list: also the user's own daily search limit."""

    search_daily_limit: int | None  # None means the default from settings


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'
