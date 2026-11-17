import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

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


def split_title(page_title: str) -> tuple[str, str | None]:
    """Guess (job title, company) from a page title; company is None if there is no pattern.

    'Python Developer at Codesky | LinkedIn' -> ('Python Developer', 'Codesky')
    'Python Developer - Codesky - Just Join IT' -> ('Python Developer', 'Codesky')
    """
    text = page_title.split(' | ')[0].strip()
    if ' at ' in text:
        title, company = text.rsplit(' at ', 1)
        return title.strip(), company.strip() or None
    parts = DASH.split(text)
    if len(parts) > 1:
        return parts[0].strip(), parts[1].strip() or None
    return text, None


def host_of(url: object) -> str | None:
    """The site's host without 'www.', e.g. 'justjoin.it'; used when no company is found."""
    if not isinstance(url, str):
        return None
    host = urlsplit(url).hostname
    return host.removeprefix('www.') if host else None


def to_offer(row: object) -> JobOfferImport | None:
    """Turn one Tavily result into an offer, best effort; None if it isn't a valid offer."""
    if not isinstance(row, dict):
        return None
    title, company = split_title(str(row.get('title') or ''))
    try:
        return JobOfferImport.model_validate(
            {
                'title': title[:200],
                'company_name': company or host_of(row.get('url')),
                'url': row.get('url'),
                'description': row.get('content') or None,
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
