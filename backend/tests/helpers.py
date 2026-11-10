"""Plain helpers and constants shared by test files (fixtures live in conftest.py)."""

USER_EMAIL = 'user@example.com'
ADMIN_EMAIL = 'admin@example.com'
PASSWORD = 'user12345'


def auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}
