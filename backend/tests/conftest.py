from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.dependencies import get_db
from app.main import app
from app.models import Role, User
from app.models.role import RoleName
from tests.helpers import ADMIN_EMAIL, PASSWORD, USER_EMAIL

TEST_DATABASE_URL = make_url(settings.database_url).set(database='job_radar_test')


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope='session')
def engine() -> Generator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(Role), [{'name': 'user'}, {'name': 'admin'}])
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode='create_savepoint', autoflush=False)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def api(client: TestClient, db: Session) -> Generator[TestClient]:
    """A test client whose routes use the test database session instead of the real one."""
    app.dependency_overrides[get_db] = lambda: db
    yield client
    app.dependency_overrides.clear()


def register_and_login(api: TestClient, email: str) -> tuple[int, str]:
    """Register a user through the API, log in, and return (user id, access token)."""
    response = api.post('/auth/register', json={'email': email, 'password': PASSWORD})
    user_id = int(response.json()['id'])
    response = api.post('/auth/login', data={'username': email, 'password': PASSWORD})
    return user_id, str(response.json()['access_token'])


@pytest.fixture
def registered_user_id(api: TestClient) -> int:
    response = api.post('/auth/register', json={'email': USER_EMAIL, 'password': PASSWORD})
    return int(response.json()['id'])


@pytest.fixture
def access_token(api: TestClient, registered_user_id: int) -> str:
    del registered_user_id  # requested only so the user is registered before logging in
    response = api.post('/auth/login', data={'username': USER_EMAIL, 'password': PASSWORD})
    return str(response.json()['access_token'])


@pytest.fixture
def admin_token(api: TestClient, db: Session) -> str:
    """A token for a user promoted to admin directly in the database.

    The API never lets anyone register as an admin, so the test does it behind the API's back.
    The route and the test share the same `db` session, so the change is visible to the next
    request, and it is rolled back after the test like everything else.
    """
    user_id, token = register_and_login(api, ADMIN_EMAIL)

    admin_role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN))
    user = db.get(User, user_id)
    assert admin_role is not None
    assert user is not None
    user.role = admin_role  # set the relationship, so a cached `user.role` can't go stale
    db.flush()

    return token
