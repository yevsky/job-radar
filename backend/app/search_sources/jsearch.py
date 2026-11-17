from typing import Any

import httpx
from pydantic import ValidationError

from app.core.levels import guess_level
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import PostedWithin, SearchQuery
from app.search_sources.base import SearchSource, SearchSourceError

# OpenWeb Ninja's own API (the same JSearch is also sold on RapidAPI, with other headers).
JSEARCH_URL = 'https://api.openwebninja.com/jsearch/search-v2'
TIMEOUT_SECONDS = 15

# Our employment types -> JSearch's. B2B has no JSearch value, so it is left out of the filter.
TO_JSEARCH = {
    EmploymentType.FULL_TIME: 'FULLTIME',
    EmploymentType.PART_TIME: 'PARTTIME',
    EmploymentType.CONTRACT: 'CONTRACTOR',
    EmploymentType.INTERNSHIP: 'INTERN',
}
FROM_JSEARCH = {value: key for key, value in TO_JSEARCH.items()}

DATE_POSTED = {
    PostedWithin.DAY: 'today',
    PostedWithin.WEEK: 'week',
    PostedWithin.MONTH: 'month',
}

# The wanted level -> JSearch's experience filter. Middle has none: it spans both sides of 3 years.
JOB_REQUIREMENTS = {
    ExperienceLevel.TRAINEE: 'no_experience',
    ExperienceLevel.JUNIOR: 'under_3_years_experience',
    ExperienceLevel.SENIOR: 'more_than_3_years_experience',
    ExperienceLevel.LEAD: 'more_than_3_years_experience',
}


def location_of(job: dict[str, Any]) -> str | None:
    """'Remote' for a remote job, else JSearch's 'City, Region, Country', else city and country."""
    if job.get('job_is_remote'):
        return 'Remote'
    location = job.get('job_location')
    if isinstance(location, str) and location.strip():
        return location.strip()[:100]
    parts = [job.get('job_city'), job.get('job_country')]
    text = ', '.join(part for part in parts if isinstance(part, str) and part.strip())
    return text[:100] or None


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

    def __init__(
        self, api_key: str, country: str = 'pl', client: httpx.Client | None = None
    ) -> None:
        self.api_key = api_key
        self.country = country  # JSearch searches the US unless told otherwise
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)  # tests pass their own

    def build_params(self, query: SearchQuery) -> dict[str, str]:
        """The query string of the request: the phrase plus JSearch's own filters."""
        params = {'query': query.text(), 'num_pages': '1', 'country': self.country}
        types = [TO_JSEARCH[t] for t in query.employment_types if t in TO_JSEARCH]
        if types:
            params['employment_types'] = ','.join(types)
        if query.remote_only:
            params['work_from_home'] = 'true'
        if query.posted_within:
            params['date_posted'] = DATE_POSTED[query.posted_within]
        wanted = query.wanted_level()
        if wanted in JOB_REQUIREMENTS:
            params['job_requirements'] = JOB_REQUIREMENTS[wanted]
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

    def search(self, query: SearchQuery, limit: int) -> list[JobOfferImport]:
        jobs = self.send(self.build_params(query))
        offers = [offer for job in jobs if (offer := to_offer(job)) is not None]
        return offers[:limit]

    def test(self) -> bool:
        try:
            self.send({'query': 'python developer', 'num_pages': '1', 'country': self.country})
        except SearchSourceError:
            return False
        return True
