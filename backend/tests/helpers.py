"""Plain helpers and constants shared by test files (fixtures live in conftest.py)."""

from app.models import JobOffer
from app.models.enums import SourceKind

USER_EMAIL = 'user@example.com'
ADMIN_EMAIL = 'admin@example.com'
PASSWORD = 'user12345'


def auth_header(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def make_offer(url: str = 'https://example.com/jobs/1', **overrides: object) -> JobOffer:
    """A valid job offer with only the required fields filled in."""
    fields: dict[str, object] = {
        'title': 'Backend Developer',
        'company_name': 'Codesky',
        'source': SourceKind.MANUAL,
        'url': url,
    }
    fields.update(overrides)
    return JobOffer(**fields)
