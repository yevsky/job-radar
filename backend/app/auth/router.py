from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.schemas import Token, UserRead, UserRegister
from app.auth.service import EmailAlreadyRegisteredError, authenticate_user, register_user
from app.auth.token import create_access_token
from app.db.dependencies import get_db
from app.models import User

router = APIRouter(prefix='/auth', tags=['auth'])

DbSession = Annotated[Session, Depends(get_db)]


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
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> Token:
    """Exchange email and password for an access token."""
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect email or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    return Token(access_token=create_access_token(str(user.id)))
