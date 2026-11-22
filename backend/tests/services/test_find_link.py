import pytest

from app.services.offer_parsing import find_link


@pytest.mark.parametrize(
    ('text', 'link'),
    [
        (
            'Apply: https://justjoin.it/job-offer/codesky-python',
            'https://justjoin.it/job-offer/codesky-python',
        ),
        ('Apply at https://codesky.pl/careers/42.', 'https://codesky.pl/careers/42'),
        ('Links: https://a.pl/1, https://b.pl/2', 'https://a.pl/1'),
        ('(see https://codesky.pl/jobs?id=7&ref=li)', 'https://codesky.pl/jobs?id=7&ref=li'),
        ('<a href="https://codesky.pl/job">Apply</a>', 'https://codesky.pl/job'),
        ('HTTP://CODESKY.PL/JOB', 'HTTP://CODESKY.PL/JOB'),
        ('http://localhost:8000/x then https://codesky.pl/job', 'https://codesky.pl/job'),
    ],
    ids=['plain', 'full-stop', 'first-of-two', 'brackets', 'html', 'upper-case', 'no-dot-host'],
)
def test_first_link_is_found(text: str, link: str) -> None:
    assert find_link(text) == link


@pytest.mark.parametrize(
    'text',
    [
        'Junior Python Developer, Wrocław. Send your CV to jobs@codesky.pl',
        'Visit codesky.pl or www.codesky.pl',  # no scheme: not sure it's a link
        'https://',
        'https://' + 'a' * 2050 + '.pl',
    ],
    ids=['email', 'no-scheme', 'scheme-only', 'too-long'],
)
def test_no_link_gives_none(text: str) -> None:
    assert find_link(text) is None
