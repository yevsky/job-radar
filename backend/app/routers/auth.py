from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.token import create_access_token
from app.db.dependencies import DbSession
from app.dependencies import CurrentUser
from app.models import User
from app.schemas.user import Token, UserRead, UserRegister
from app.services.auth import (
    EmailAlreadyRegisteredError,
    InvalidRefreshTokenError,
    authenticate_user,
    issue_refresh_token,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix='/auth', tags=['auth'])

# The refresh token lives in an HttpOnly cookie: JavaScript (and so an XSS bug) can't read it,
# and the browser sends it by itself to /auth/refresh. The access token stays short-lived.
REFRESH_COOKIE = 'jobradar_refresh'
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite='lax',  # not sent with requests that other sites start
        path='/',  # the frontend calls /api/auth/..., the backend sees /auth/...
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite='lax',
        path='/',
    )


@router.post('/register', response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: DbSession) -> User:
    """Create a new account."""
    try:
        user = register_user(db, data)
    except EmailAlreadyRegisteredError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail='Email already registered.'
        ) from err

    return user


@router.post('/login', response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession, response: Response
) -> Token:
    """Exchange email and password for an access token.

    Also sets the refresh cookie, so the browser stays logged in until you log out.
    """
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect email or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    set_refresh_cookie(response, issue_refresh_token(db, user))
    return Token(access_token=create_access_token(str(user.id)))


@router.post('/refresh', response_model=Token)
def refresh(db: DbSession, response: Response, refresh_token: RefreshCookie = None) -> Token:
    """A new access token from the refresh cookie, without the password.

    The cookie is replaced by a new one each time. 401 means the login ended (logged out,
    unused for too long, or the account was deleted): log in again.
    """
    try:
        if refresh_token is None:
            raise InvalidRefreshTokenError
        user, new_token = rotate_refresh_token(db, refresh_token)
    except InvalidRefreshTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Your login has ended, please log in again',
            # A route that raises loses `response`, so the cookie is cleared through headers
            headers={'set-cookie': _cleared_cookie_header()},
        ) from err

    set_refresh_cookie(response, new_token)
    return Token(access_token=create_access_token(str(user.id)))


def _cleared_cookie_header() -> str:
    cleared = Response()
    clear_refresh_cookie(cleared)
    return cleared.headers['set-cookie']


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbSession, response: Response, refresh_token: RefreshCookie = None) -> None:
    """End the login on this browser: the refresh token stops working and the cookie goes.

    Needs no access token, so logging out works even after it expired.
    """
    if refresh_token is not None:
        revoke_refresh_token(db, refresh_token)
    clear_refresh_cookie(response)


@router.get('/me', response_model=UserRead)
def read_me(user: CurrentUser) -> User:
    """Return the logged-in user's profile."""
    return user
