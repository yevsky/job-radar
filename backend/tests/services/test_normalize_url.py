import pytest

from app.services.job_offer_import import normalize_url


@pytest.mark.parametrize(
    ('url', 'expected'),
    [
        ('https://example.com/job/1', 'https://example.com/job/1'),
        ('HTTPS://Example.COM/job/1', 'https://example.com/job/1'),
        ('https://example.com/job/1/', 'https://example.com/job/1'),
        ('https://example.com/job/1#apply', 'https://example.com/job/1'),
        ('https://example.com/job/1?utm_source=x&utm_medium=y', 'https://example.com/job/1'),
        ('https://Example.com/job/1/?utm_source=x#apply', 'https://example.com/job/1'),
        ('https://example.com/job/1?id=7&utm_source=x', 'https://example.com/job/1?id=7'),
        ('https://www.example.com/job/1', 'https://example.com/job/1'),
        ('https://example.com/job/1?trk=a&gclid=b&ref=c&fbclid=d', 'https://example.com/job/1'),
        ('https://example.com/job/1?b=2&a=1', 'https://example.com/job/1?a=1&b=2'),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_path_keeps_its_letter_case() -> None:
    # Only the host is case-insensitive; on many sites /Job/ABC and /job/abc are different pages.
    assert normalize_url('https://example.com/Job/ABC') == 'https://example.com/Job/ABC'
