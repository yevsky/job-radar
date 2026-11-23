from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.ai.base import AIProvider
from app.ai.registry import build_provider
from app.core.config import settings
from app.core.token import decode_access_token
from app.db.dependencies import DbSession
from app.models import User
from app.models.role import RoleName
from app.search_sources.base import SearchSource
from app.search_sources.page_reader import PageReader, build_page_reader
from app.search_sources.registry import build_sources
from app.services.search import enabled_sources

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    """Return the user the bearer token belongs to, or raise 401."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        user_id = int(decode_access_token(token))
    except (jwt.InvalidTokenError, KeyError, ValueError) as err:
        raise credentials_error from err

    user = db.get(User, user_id)
    if user is None:
        raise credentials_error

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str) -> Callable[[User], User]:
    """Return a dependency that lets in only users with one of the given roles."""

    def check_role(user: CurrentUser) -> User:
        if user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Not enough permissions',
            )
        return user

    return check_role


# The logged-in user, who must be an admin (403 otherwise)
CurrentAdmin = Annotated[User, Depends(require_role(RoleName.ADMIN))]


search_sources = build_sources(settings.search_sources)


def get_search_sources() -> list[SearchSource]:
    """The enabled search sources; tests replace this with fake ones."""
    return search_sources


SearchSources = Annotated[list[SearchSource], Depends(get_search_sources)]


def get_enabled_search_sources(sources: SearchSources, db: DbSession) -> list[SearchSource]:
    """The server's sources minus the ones an admin switched off: what searches may ask."""
    return enabled_sources(db, sources)


# Use this for anything a user runs; SearchSources (all of them) is for the admin pages
EnabledSearchSources = Annotated[list[SearchSource], Depends(get_enabled_search_sources)]


ai_provider = build_provider(settings.ai_provider)


def get_ai_provider() -> AIProvider:
    """The AI provider chosen in AI_PROVIDER; tests replace this with a fake one."""
    return ai_provider


AI = Annotated[AIProvider, Depends(get_ai_provider)]


page_reader = build_page_reader(settings.tavily_api_key)


def get_page_reader() -> PageReader | None:
    """Reads full posting pages (Tavily Extract); None without a Tavily key."""
    return page_reader


Pages = Annotated[PageReader | None, Depends(get_page_reader)]
