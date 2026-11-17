import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.levels import guess_level
from app.models.enums import EmploymentType
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import SearchQuery
from app.search_sources.base import SearchSource, SearchSourceError

TAVILY_URL = 'https://api.tavily.com/search'
TIMEOUT_SECONDS = 15
MAX_RESULTS = 20

# Tavily has no employment type filter, so these words are added to the phrase instead.
EMPLOYMENT_WORDS = {
    EmploymentType.FULL_TIME: 'full-time',
    EmploymentType.PART_TIME: 'part-time',
    EmploymentType.CONTRACT: 'contract',
    EmploymentType.INTERNSHIP: 'internship',
    EmploymentType.B2B: 'B2B',
}

# "Python Developer - Codesky" or "Python Developer – Codesky"
DASH = re.compile(r'\s[-–—]\s')

# The path of ONE offer on each job board. Other pages there (search results, categories
# like nofluffjobs.com/django) list many offers, so they are skipped. Other sites are kept.
OFFER_PATHS = {
    'justjoin.it': re.compile(r'^/job-offer/'),
    'nofluffjobs.com': re.compile(r'^/(?:[a-z]{2}/)?job/'),
    'pracuj.pl': re.compile(r'^/praca/.+,oferta,\d+'),
    'linkedin.com': re.compile(r'^/jobs/view/'),
}

# Site names that page titles end with; never a company.
SITE_NAMES = {
    'just join it',
    'justjoin.it',
    'no fluff jobs',
    'nofluffjobs',
    'pracuj.pl',
    'linkedin',
}

# Words some boards add to the title: 'Python Developer Job' -> 'Python Developer'
TITLE_SUFFIX = re.compile(r'\s+(?:job|job offer)$', re.IGNORECASE)


def host_of(url: object) -> str | None:
    """The site's host without 'www.', e.g. 'justjoin.it'; used when no company is found."""
    if not isinstance(url, str):
        return None
    host = urlsplit(url).hostname
    return host.removeprefix('www.') if host else None


def board_of(host: str) -> str | None:
    """The job board a host belongs to ('pl.linkedin.com' -> 'linkedin.com'), if any."""
    return next((b for b in OFFER_PATHS if host == b or host.endswith(f'.{b}')), None)


def is_offer_page(url: object) -> bool:
    """False for a job board page that lists many offers instead of showing one."""
    host = host_of(url)
    board = board_of(host) if host else None
    if board is None:
        return True
    return bool(OFFER_PATHS[board].match(urlsplit(str(url)).path))


def split_title(page_title: str) -> tuple[str, str | None]:
    """Guess (job title, company) from a page title; company is None if there is no pattern.

    'Python Developer at Codesky | LinkedIn' -> ('Python Developer', 'Codesky')
    'Python Developer - Codesky - Just Join IT' -> ('Python Developer', 'Codesky')
    'Python Developer - Just Join IT' -> ('Python Developer', None)
    'Python Developer at Codesky — Wrocław - LinkedIn' -> ('Python Developer', 'Codesky')
    """
    text = page_title.split(' | ')[0].strip().removesuffix('...').removesuffix('…').strip()
    title, company = text, None
    if ' at ' in text:
        title, company = text.rsplit(' at ', 1)
    else:
        parts = DASH.split(text)
        if len(parts) > 1:
            title, company = parts[0], parts[1]
    # LinkedIn adds a place and the site after the company: 'Codesky — Wrocław - LinkedIn'
    company = DASH.split(company or '')[0].strip()
    if company.lower() in SITE_NAMES:
        company = ''
    return TITLE_SUFFIX.sub('', title.strip()), company or None


def slugify(text: str) -> str:
    """'Python Developer (Azure)' -> 'python-developer-azure', the way job boards write links."""
    return '-'.join(re.findall(r'[a-z0-9]+', text.lower()))


def company_from_url(url: object, title: str) -> str | None:
    """Guess the company from the last part of an offer link; None if there is no pattern.

    LinkedIn:      .../senior-python-developer-at-codesky-4306190000  -> 'Codesky'
    Just Join IT:  .../codesky-python-developer-warszawa-python        -> company, then title
    No Fluff Jobs: .../python-developer-codesky-warszawa-1             -> title, company, city
    """
    if not isinstance(url, str):
        return None
    slug = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1].lower()
    slug = re.sub(r'-\d+$', '', slug)  # drop a trailing id or number
    title_slug = slugify(title)
    position = slug.find(title_slug) if title_slug else -1

    if '-at-' in slug:
        company = slug.rsplit('-at-', 1)[1]
    elif position > 0:
        company = slug[:position]
    elif position == 0 and board_of(host_of(url) or '') == 'nofluffjobs.com':
        words = slug[len(title_slug) :].strip('-').split('-')
        company = '-'.join(words[:-1])  # the last word is the city
    else:
        company = ''
    return company.strip('-').replace('-', ' ').title() or None


def to_offer(row: object) -> JobOfferImport | None:
    """Turn one Tavily result into an offer, best effort; None if it isn't a single offer."""
    if not isinstance(row, dict) or not is_offer_page(row.get('url')):
        return None
    url = row.get('url')
    title, company = split_title(str(row.get('title') or ''))
    description = row.get('content') or None
    try:
        return JobOfferImport.model_validate(
            {
                'title': title[:200],
                'company_name': company or company_from_url(url, title) or host_of(url),
                'url': url,
                'experience_level': guess_level(title, str(description or '')),
                'description': description,
            }
        )
    except ValidationError:
        return None


class TavilySource(SearchSource):
    """Web search through Tavily. It returns pages, not job data, so mapping is best effort."""

    name = 'tavily'

    def __init__(
        self, api_key: str, domains: list[str], client: httpx.Client | None = None
    ) -> None:
        self.api_key = api_key
        self.domains = domains
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)  # tests pass their own

    def build_body(self, query: SearchQuery, limit: int) -> dict[str, Any]:
        """The JSON body of the request: the phrase plus Tavily's own filters."""
        words = [query.text(), *(EMPLOYMENT_WORDS[t] for t in query.employment_types)]
        body: dict[str, Any] = {
            'query': ' '.join(word for word in words if word),
            'max_results': min(limit, MAX_RESULTS),
        }
        if query.posted_within:
            body['time_range'] = query.posted_within.value  # Tavily uses the same day/week/month
        if self.domains:
            body['include_domains'] = self.domains
        return body

    def send(self, body: dict[str, Any]) -> list[Any]:
        """POST the body to Tavily and return its 'results' list; raise SearchSourceError."""
        try:
            response = self.client.post(
                TAVILY_URL,
                json=body,
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json()['results']
        except httpx.HTTPStatusError as err:
            raise SearchSourceError(f'Tavily answered {err.response.status_code}') from err
        except httpx.HTTPError as err:  # timeout, no connection, ...
            raise SearchSourceError(f'Tavily could not be reached: {type(err).__name__}') from err
        except (ValueError, KeyError, TypeError) as err:  # not JSON, or no 'results'
            raise SearchSourceError('Tavily sent a response we could not read') from err

        if not isinstance(results, list):
            raise SearchSourceError('Tavily sent a response we could not read')
        return results

    def search(self, query: SearchQuery, limit: int) -> list[JobOfferImport]:
        rows = self.send(self.build_body(query, limit))
        offers = [offer for row in rows if (offer := to_offer(row)) is not None]
        return offers[:limit]

    def test(self) -> bool:
        try:
            self.send({'query': 'python developer', 'max_results': 1})
        except SearchSourceError:
            return False
        return True
