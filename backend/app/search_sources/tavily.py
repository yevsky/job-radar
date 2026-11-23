import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.levels import guess_level
from app.core.locations import CITIES, COUNTRIES, REMOTE_WORDS, guess_location, normalize
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import HiddenReason, SearchQuery, SourceFeature
from app.search_sources.base import HiddenOffer, SearchSource, SearchSourceError, SourcePage

TAVILY_URL = 'https://api.tavily.com/search'
TIMEOUT_SECONDS = 15
MAX_RESULTS = 100  # the most Tavily returns for one search; it has no pages of its own
MAX_DESCRIPTION = 20_000  # JobOfferImport.description's limit

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

# Words a page title can be made of when it names only a place, like 'Wroclaw': the title a
# job board gives the list page it redirects an expired offer to.
PLACE_WORDS = {
    word
    for spellings in [s for _name, s in CITIES] + [list(COUNTRIES.values()), REMOTE_WORDS]
    for spelling in spellings
    for word in spelling.split()
} | {'poland', 'polska'}

# What a page says when the offer is closed (compared after normalize(): no diacritics)
CLOSED_PHRASES = [
    'no longer accepting applications',
    'this job is no longer available',
    'this offer is no longer available',
    'this job offer has expired',
    'this offer has expired',
    'offer expired',
    'nie przyjmuje juz aplikacji',
    'nie przyjmujemy juz aplikacji',
    'oferta wygasla',
    'ogloszenie wygaslo',
    'oferta jest nieaktualna',
    'ogloszenie jest nieaktualne',
    'rekrutacja zakonczona',
]
# The offer's status is near the top of the page; further down come other offers
CLOSED_CHECK_CHARS = 3_000

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


# Titles of pages that list many offers: 'Python Jobs in Warsaw', '11,000+ Open Roles', and
# No Fluff Jobs' category pages: 'Python Jobs | IT jobs | Wroclaw | Fresh offers with salary
# ranges' or 'Praca Python | Praca IT | Wrocław | Najnowsze oferty z widełkami wynagrodzeń'
LIST_TITLE = re.compile(
    r'\b(?:\d[\d,.]*\+?\s+(?:new\s+|open\s+)?(?:jobs|roles|positions|offers|ofert)'
    r'|jobs\s+in|job\s+offers\s+in|oferty\s+pracy)\b'
    r'|\|\s*(?:it\s+jobs|praca\s+it)\s*\|'
    r'|\bfresh\s+offers\b|\bnajnowsze\s+oferty\b',
    re.IGNORECASE,
)

# Words some boards put before the job title: 'Praca Junior Python Developer | ...' on
# No Fluff Jobs, 'Oferta pracy Junior Python Developer, Capgemini, Wrocław' on Pracuj.pl
TITLE_PREFIX = re.compile(r'^(?:oferta\s+pracy|praca)\s+', re.IGNORECASE)


def is_offer_link(url: object) -> bool:
    """True if the link has the shape of one offer on a job board we know."""
    host = host_of(url)
    board = board_of(host) if host else None
    return board is not None and bool(OFFER_PATHS[board].match(urlsplit(str(url)).path))


def is_offer_page(url: object, page_title: str = '') -> bool:
    """False for a page that lists many offers instead of showing one: a job board's list
    path, or any site's title like 'Python Jobs in Warsaw (1,200 open roles)'."""
    if LIST_TITLE.search(page_title):
        return False
    host = host_of(url)
    board = board_of(host) if host else None
    if board is None:
        return True
    return bool(OFFER_PATHS[board].match(urlsplit(str(url)).path))


def is_only_a_place(text: str) -> bool:
    """True for 'Wroclaw' or 'Wrocław, Poland': a place name, not a job title or company."""
    words = normalize(text).split()
    return bool(words) and all(word in PLACE_WORDS for word in words)


def is_closed(*texts: str) -> bool:
    """True if the page says the offer no longer takes applications."""
    words = ' '.join(normalize(text[:CLOSED_CHECK_CHARS]) for text in texts)
    return any(f' {phrase} ' in f' {words} ' for phrase in CLOSED_PHRASES)


def page_text(raw: object) -> str | None:
    """The full page text Tavily read, without blank lines and cut to the description's
    limit; None if it sent none."""
    if not isinstance(raw, str):
        return None
    lines = [line.strip() for line in raw.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text[:MAX_DESCRIPTION] or None


def split_title(page_title: str) -> tuple[str, str | None]:
    """Guess (job title, company) from a page title; company is None if there is no pattern.

    'Praca Python Developer | Backend | Codesky | Wrocław | No Fluff Jobs.'
        -> ('Python Developer', 'Codesky')
    'Oferta pracy Python Developer, Codesky, Wrocław' -> ('Python Developer', 'Codesky')

    'Python Developer at Codesky | LinkedIn' -> ('Python Developer', 'Codesky')
    'Python Developer - Codesky - Just Join IT' -> ('Python Developer', 'Codesky')
    'Python Developer - Just Join IT' -> ('Python Developer', None)
    'Python Developer at Codesky — Wrocław - LinkedIn' -> ('Python Developer', 'Codesky')
    'Python Developer w firmie Codesky - Wrocław' -> ('Python Developer', 'Codesky')
    """
    segments = [s.strip() for s in page_title.split(' | ')]
    text = segments[0].removesuffix('...').removesuffix('…').strip()
    prefixed = TITLE_PREFIX.match(text)
    text = TITLE_PREFIX.sub('', text)
    title, company = text, None
    # No Fluff Jobs: 'Praca <title> | <category> | <company> | <city> | No Fluff Jobs.'
    if len(segments) >= 5 and 'no fluff jobs' in segments[-1].lower():
        title, company = text, segments[2]
    # Pracuj.pl: 'Oferta pracy <title>, <company>, <city>'
    elif prefixed and text.count(', ') >= 1:
        title, company = text.split(', ')[:2]
    elif ' at ' in text:
        title, company = text.rsplit(' at ', 1)
    elif ' w firmie ' in text:  # Polish: 'at the company'
        title, company = text.rsplit(' w firmie ', 1)
    else:
        parts = DASH.split(text)
        if len(parts) > 1:
            title, company = parts[0], parts[1]
    # LinkedIn adds a place and the site after the company: 'Codesky — Wrocław - LinkedIn'
    company = DASH.split(company or '')[0].strip()
    if company.lower() in SITE_NAMES or is_only_a_place(company):  # 'Python Dev - Wrocław'
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


def location_from_url(url: object, page_title: str, wanted: list[str] | None = None) -> str | None:
    """Guess the city from the offer link or the page title; Tavily sends no location.

    Job boards put the city in the link ('.../codesky-python-developer-warszawa-python')
    and LinkedIn in the title ('Python Developer at Codesky — Wrocław - LinkedIn').
    """
    slug = urlsplit(url).path if isinstance(url, str) else ''
    return guess_location(slug, page_title, wanted=wanted)


def read_row(
    row: object, wanted: list[str] | None = None
) -> tuple[JobOfferImport | None, HiddenReason | None]:
    """One Tavily result as an offer, best effort, and why it should be hidden, if it should:
    a list page, a closed offer, or an expired one the board redirects to a list.
    (None, None) if it can't be read at all.

    `wanted` are the cities the user asked for, so a city we don't list is found too.
    """
    if not isinstance(row, dict):
        return None, None
    url = row.get('url')
    page_title = str(row.get('title') or '')
    title, company = split_title(page_title)
    snippet = str(row.get('content') or '')
    full_text = page_text(row.get('raw_content'))
    try:
        offer = JobOfferImport.model_validate(
            {
                'title': title[:200],
                'company_name': company or company_from_url(url, title) or host_of(url),
                'url': url,
                'location': location_from_url(url, page_title, wanted),
                # the snippet, not the page: pages also list other offers with their levels
                'experience_level': guess_level(title, snippet),
                # the whole posting when Tavily read it, for the analysis and the save
                'description': full_text or snippet or None,
            }
        )
    except ValidationError:
        return None, None
    if is_offer_link(url) and LIST_TITLE.search(page_title):
        # an offer's link, but the board answered with a list page: the offer expired
        return offer, HiddenReason.EXPIRED
    if not is_offer_page(url, page_title):
        return offer, HiddenReason.LIST_PAGE
    if is_only_a_place(title):
        return offer, HiddenReason.EXPIRED
    if is_closed(snippet, full_text or ''):
        return offer, HiddenReason.CLOSED
    return offer, None


def to_offer(row: object, wanted: list[str] | None = None) -> JobOfferImport | None:
    """The result as an offer, or None if it isn't one open offer (see read_row)."""
    offer, reason = read_row(row, wanted)
    return offer if reason is None else None


class TavilySource(SearchSource):
    """Web search through Tavily. It returns pages, not job data, so mapping is best effort."""

    name = 'tavily'
    # No country: include_domains already picks the job boards, and the cities are in the
    # phrase. No pages: Tavily can't skip results, so one search asks for all MAX_RESULTS
    # (a basic search costs 1 credit whatever the count).
    features = frozenset({SourceFeature.POSTED_WITHIN})

    def __init__(
        self, api_key: str, domains: list[str], client: httpx.Client | None = None
    ) -> None:
        self.api_key = api_key
        self.domains = domains
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)  # tests pass their own

    def build_body(self, query: SearchQuery) -> dict[str, Any]:
        """The JSON body of the request: the phrase plus Tavily's own filters.

        Always the most results Tavily gives: many are list pages or other cities and get
        left out, so asking for fewer left almost nothing to show.
        """
        body: dict[str, Any] = {
            'query': query.text(),
            'max_results': MAX_RESULTS,
            # each page's full text too, at no extra credit: the snippet is ~300 characters
            'include_raw_content': 'text',
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

    def search(self, query: SearchQuery, limit: int) -> SourcePage:
        """Everything Tavily found, on page 1; `limit` is not used, since the results that
        survive the filters are few. Later pages are empty and cost no credit."""
        del limit
        if query.page > 1:
            return SourcePage()
        rows = self.send(self.build_body(query))
        page = SourcePage()
        for row in rows:
            offer, reason = read_row(row, query.cities())
            if offer is None:
                page.skipped += 1  # broken rows count as hidden, but can't be shown
            elif reason is None:
                page.offers.append(offer)
            else:
                page.hidden.append(HiddenOffer(offer, reason))
        return page

    def test(self) -> bool:
        try:
            self.send({'query': 'python developer', 'max_results': 1})
        except SearchSourceError:
            return False
        return True
