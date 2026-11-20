from typing import Any

import httpx
from pydantic import ValidationError

from app.core.levels import guess_level
from app.models.enums import EmploymentType
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import PostedWithin, SearchQuery, SourceFeature
from app.search_sources.base import SearchSource, SearchSourceError, SourcePage

# OpenWeb Ninja's own API
JSEARCH_URL = 'https://api.openwebninja.com/jsearch/search-v2'
TIMEOUT_SECONDS = 15
JSEARCH_PAGE_SIZE = 10

# JSearch's employment types -> ours (B2B has no JSearch value)
FROM_JSEARCH = {
    'FULLTIME': EmploymentType.FULL_TIME,
    'PARTTIME': EmploymentType.PART_TIME,
    'CONTRACTOR': EmploymentType.CONTRACT,
    'INTERN': EmploymentType.INTERNSHIP,
}

DATE_POSTED = {
    PostedWithin.DAY: 'today',
    PostedWithin.WEEK: 'week',
    PostedWithin.MONTH: 'month',
}


def location_of(job: dict[str, Any]) -> str | None:
    """JSearch's 'City, Region, Country', else city and country; '(remote)' added for a
    remote job, so the city still counts in the city filter. Just 'Remote' without a place."""
    location = job.get('job_location')
    if not isinstance(location, str) or not location.strip():
        parts = [job.get('job_city'), job.get('job_country')]
        location = ', '.join(part for part in parts if isinstance(part, str) and part.strip())
    location = location.strip()
    if job.get('job_is_remote'):
        location = f'{location[:90]} (remote)' if location else 'Remote'
    return location[:100] or None


def employment_type_of(job: dict[str, Any]) -> EmploymentType | None:
    """The first type we know from job_employment_types (['FULLTIME']); None for 'TEMPORARY'."""
    types = job.get('job_employment_types')
    if not isinstance(types, list):
        types = [job.get('job_employment_type')]
    known = [FROM_JSEARCH[t] for t in types if isinstance(t, str) and t in FROM_JSEARCH]
    return known[0] if known else None


def skills_of(job: dict[str, Any]) -> list[str]:
    """job_required_skills when JSearch has them; names that don't fit our limit are dropped."""
    skills = job.get('job_required_skills')
    if not isinstance(skills, list):
        return []
    return [s for s in skills if isinstance(s, str) and len(s.strip()) <= 50]


def to_offer(job: object) -> JobOfferImport | None:
    """Turn one JSearch job into an offer; None if it isn't a valid offer."""
    if not isinstance(job, dict):
        return None
    description = job.get('job_description')
    if not isinstance(description, str):
        description = None
    title = job.get('job_title')
    try:
        return JobOfferImport.model_validate(
            {
                'title': title,
                'company_name': job.get('employer_name'),
                'url': job.get('job_apply_link'),
                'location': location_of(job),
                'employment_type': employment_type_of(job),
                'experience_level': guess_level(str(title or ''), description),
                'description': description[:20_000] if description else None,
                'technologies': skills_of(job),
                'deadline': job.get('job_offer_expiration_datetime_utc'),
            }
        )
    except ValidationError:
        return None


class JSearchSource(SearchSource):
    """Job postings through JSearch (OpenWeb Ninja): structured data, so mapping is direct."""

    name = 'jsearch'
    features = frozenset(SourceFeature)  # country, date_posted and page are JSearch filters

    def __init__(
        self, api_key: str, country: str = 'pl', client: httpx.Client | None = None
    ) -> None:
        self.api_key = api_key
        self.country = country  # for test(); a search sends the form's country
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)  # tests pass their own

    def build_params(self, query: SearchQuery) -> dict[str, str]:
        """The query string of the request: the phrase plus JSearch's own filters."""
        # No job_requirements: Google Jobs rarely tags offers outside the US with experience,
        # so that filter returned 0 jobs for Poland. The level is a word in the position, and
        # the level filter in collect_results drops offers far from it.
        params = {
            'query': query.text(),
            'page': str(query.page),
            'num_pages': '1',
            'country': query.country,  # JSearch searches the US unless told otherwise
        }
        if query.posted_within:
            params['date_posted'] = DATE_POSTED[query.posted_within]
        return params

    def send(self, params: dict[str, str]) -> list[Any]:
        """GET JSearch with the params and return its jobs list; raise SearchSourceError."""
        try:
            response = self.client.get(
                JSEARCH_URL,
                params=params,
                headers={'x-api-key': self.api_key},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            jobs = response.json()['data']['jobs']
        except httpx.HTTPStatusError as err:
            raise SearchSourceError(f'JSearch answered {err.response.status_code}') from err
        except httpx.HTTPError as err:  # timeout, no connection, ...
            raise SearchSourceError(f'JSearch could not be reached: {type(err).__name__}') from err
        except (ValueError, KeyError, TypeError) as err:  # not JSON, or no data.jobs
            raise SearchSourceError('JSearch sent a response we could not read') from err

        if not isinstance(jobs, list):
            raise SearchSourceError('JSearch sent a response we could not read')
        return jobs

    def search(self, query: SearchQuery, limit: int) -> SourcePage:
        jobs = self.send(self.build_params(query))
        offers = [offer for job in jobs if (offer := to_offer(job)) is not None]
        # a JSearch page holds 10 jobs; a full page means the next one may have more
        return SourcePage(offers=offers[:limit], has_more=len(jobs) >= JSEARCH_PAGE_SIZE)

    def test(self) -> bool:
        try:
            self.send({'query': 'python developer', 'num_pages': '1', 'country': self.country})
        except SearchSourceError:
            return False
        return True
