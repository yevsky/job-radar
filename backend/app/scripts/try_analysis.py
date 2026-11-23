"""Analyse one sample offer with the AI provider from .env and show every step of the score.

Run from backend/:  uv run python -m app.scripts.try_analysis

Prints step 1 (the requirements the model found, their kind and skill), the facts code
gives to step 2, step 2's judgement and the points of each rubric part.
Change SAMPLE_OFFER / SAMPLE_PROFILE to try your own case.
"""

import time

from app.ai.base import AIProviderError
from app.ai.prompts import (
    OFFER_ANALYSIS_VERSION,
    offer_judgement_messages,
    offer_requirements_messages,
)
from app.ai.structured import AIOutputError, generate
from app.dependencies import ai_provider
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import OfferAnalysisOutput, OfferJudgementOutput, OfferRequirementsOutput
from app.schemas.job_offer import JobOfferImport
from app.schemas.profile import ProfileRead
from app.services.analysis import (
    consistent_red_flags,
    facts_text,
    match_skills,
    score_breakdown,
    with_offer_technologies,
)

SAMPLE_OFFER = JobOfferImport.model_validate(
    {
        'title': 'Junior Python Developer',
        'company_name': 'Codesky',
        'url': 'https://example.com/jobs/1',
        'location': 'Wroclaw',
        'description': (
            'We build REST APIs. Required: 6-12 months of commercial experience with Python, '
            'basic experience with FastAPI, PostgreSQL, understanding what SOLID & DRY stand '
            'for. You are knowledge hungry. Nice to have: Docker. English B2. '
            'Unpaid 2-week trial before signing.'
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
    skills=['Python', 'FastAPI', 'SOLID'],
)


def main() -> None:
    provider = ai_provider
    print(f'{provider.name}/{provider.model}, prompt {OFFER_ANALYSIS_VERSION}')
    offer, profile = SAMPLE_OFFER, SAMPLE_PROFILE

    started = time.perf_counter()
    step = 1
    try:
        found = generate(
            provider, offer_requirements_messages(offer, profile), OfferRequirementsOutput
        )
        requirements = with_offer_technologies(found.requirements, offer.technologies)
        print(f'Step 1 took {time.perf_counter() - started:.1f} s\n')
        print('Requirements the model found:')
        for r in requirements:
            need = 'required' if r.required else 'nice    '
            print(f'  {need}  {r.kind:<10}  {r.text:<40}  skill: {r.skill}')

        facts = facts_text(offer, profile, requirements)
        print(f'\nFacts for step 2:\n{facts}\n')
        started = time.perf_counter()
        step = 2
        judgement = generate(
            provider, offer_judgement_messages(offer, profile, facts), OfferJudgementOutput
        )
        print(f'Step 2 took {time.perf_counter() - started:.1f} s\n')
    except (AIProviderError, AIOutputError) as err:
        print(f'Step {step} failed after {time.perf_counter() - started:.1f} s: {err}')
        return

    output = OfferAnalysisOutput(requirements=requirements, **judgement.model_dump())
    matched, missing = match_skills(requirements, profile.skills)
    breakdown = score_breakdown(offer, profile, output)
    print(f'Matched: {matched}\nMissing: {missing}\n')
    for part, points in breakdown.model_dump().items():
        print(f'  {part:<20} {points}')
    print(f'  {"total":<20} {breakdown.total}\n')
    print(f'role_fit {judgement.role_fit}: {judgement.summary}')
    for reason in judgement.reasons:
        print(f'  + {reason}')
    for flag in consistent_red_flags(judgement.red_flags, judgement.reasons, matched):
        print(f'  ! {flag}')


if __name__ == '__main__':
    main()
