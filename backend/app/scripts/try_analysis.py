"""Analyse one sample offer with the AI provider from .env and show every step of the score.

Run from backend/:  uv run python -m app.scripts.try_analysis

Prints the model's raw requirement list (what it mapped to which skill), then the points of
each rubric part. Change SAMPLE_OFFER / SAMPLE_PROFILE to try your own case.
"""

import time

from app.ai.base import AIProviderError
from app.ai.prompts import OFFER_ANALYSIS_VERSION, offer_analysis_messages
from app.ai.structured import AIOutputError, generate
from app.dependencies import ai_provider
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import OfferAnalysisOutput
from app.schemas.job_offer import JobOfferImport
from app.schemas.profile import ProfileRead
from app.services.analysis import match_skills, score_breakdown

SAMPLE_OFFER = JobOfferImport.model_validate(
    {
        'title': 'Junior Python Developer',
        'company_name': 'Codesky',
        'url': 'https://example.com/jobs/1',
        'location': 'Wroclaw',
        'description': (
            'We build REST APIs. Required: Python, FastAPI, PostgreSQL. '
            'Nice to have: Docker. English B2. Unpaid 2-week trial before signing.'
        ),
    }
)
SAMPLE_PROFILE = ProfileRead(
    first_name=None,
    last_name=None,
    bio=None,
    experience_level=ExperienceLevel.JUNIOR,
    desired_position='Python developer',
    preferred_locations=['Wrocław'],
    preferred_employment_types=[EmploymentType.B2B],
    skills=['Python', 'FastAPI'],
)


def main() -> None:
    provider = ai_provider
    print(f'{provider.name}/{provider.model}, prompt {OFFER_ANALYSIS_VERSION}')

    started = time.perf_counter()
    messages = offer_analysis_messages(SAMPLE_OFFER, SAMPLE_PROFILE)
    try:
        output = generate(provider, messages, OfferAnalysisOutput)
    except (AIProviderError, AIOutputError) as err:
        print(f'Failed: {err}')
        return
    print(f'Took {time.perf_counter() - started:.1f} s\n')

    print('Requirements the model found:')
    for requirement in output.requirements:
        kind = 'required' if requirement.required else 'nice    '
        print(f'  {kind}  {requirement.text:<40}  skill: {requirement.skill}')

    matched, missing = match_skills(output.requirements, SAMPLE_PROFILE.skills)
    breakdown = score_breakdown(SAMPLE_OFFER, SAMPLE_PROFILE, output)
    print(f'\nMatched: {matched}\nMissing: {missing}\n')
    for part, points in breakdown.model_dump().items():
        print(f'  {part:<20} {points}')
    print(f'  {"total":<20} {breakdown.total}\n')
    print(f'role_fit {output.role_fit}: {output.summary}')
    for reason in output.reasons:
        print(f'  + {reason}')
    for flag in output.red_flags:
        print(f'  ! {flag}')


if __name__ == '__main__':
    main()
