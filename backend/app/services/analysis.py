"""Match one offer against the user: the model reads the posting, code decides the score.

Two model calls. Step 1 lists the posting's requirements, each with its kind, and maps the
skills to the user's skills. Code then decides which skills the user covers and which are
missing. Step 2 gets those facts and writes the 0-10 role fit, summary, reasons and red
flags, so it can't call a skill both covered and missing. The score is a fixed rubric in code,
so the same answers always give the same score and every point can be explained:

    required skills 45 | nice-to-have 10 | level 20 | location 10 | employment type 5 | role fit 10
"""

import re

from app.ai.base import AIProvider
from app.ai.prompts import (
    OFFER_ANALYSIS_VERSION,
    offer_judgement_messages,
    offer_requirements_messages,
)
from app.ai.structured import generate
from app.core.levels import LADDER, guess_level
from app.core.locations import cities_in, city_key, is_remote, normalize
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import (
    OfferAnalysisOutput,
    OfferJudgementOutput,
    OfferRequirementsOutput,
    Requirement,
    RequirementKind,
)
from app.schemas.analysis import AnalysisResult, ScoreBreakdown
from app.schemas.job_offer import JobOfferImport
from app.schemas.profile import ProfileRead, unique_ignoring_case

REQUIRED_POINTS = 45
NICE_TO_HAVE_POINTS = 10
LEVEL_POINTS = 20
LOCATION_POINTS = 10
EMPLOYMENT_TYPE_POINTS = 5


def mentions(text: str, name: str) -> bool:
    """True if the text names it as a whole word: 'Python 3' mentions Python, 'Jython' not,
    and 'C#' or 'C++' doesn't mention C."""
    pattern = rf'(?<![\w#+.]){re.escape(name.casefold())}(?![\w#+])'
    return re.search(pattern, text.casefold()) is not None


def covering_skill(
    requirement: Requirement, skills_by_key: dict[str, str], resume_text: str | None = None
) -> str | None:
    """The user's skill that covers this requirement, if the user really has it.

    In this order: the skill the model named; the requirement itself when it is one of the
    user's skills (a small model sometimes leaves `skill` empty for 'Django'); one of the
    user's skills named inside it ('basic experience with Django' is covered by Django); the
    requirement named in the CV the user chose (then shown as the posting words it).
    Compared ignoring case. A skill that isn't in the user's list (the model made it up, or
    took it from the posting) counts as no match. Only skills are covered: a trait or years
    of experience are not something a skill list can show.
    """
    if requirement.kind != RequirementKind.SKILL:
        return None
    for name in (requirement.skill, requirement.text):
        if name is not None and (skill := skills_by_key.get(name.strip().lower())) is not None:
            return skill
    for skill in skills_by_key.values():
        if mentions(requirement.text, skill):
            return skill
    if resume_text and mentions(resume_text, requirement.text):
        return requirement.text
    return None


def skill_requirements(requirements: list[Requirement]) -> list[Requirement]:
    return [r for r in requirements if r.kind == RequirementKind.SKILL]


def with_offer_technologies(
    requirements: list[Requirement], technologies: list[str]
) -> list[Requirement]:
    """The model's requirements plus every technology the offer lists that none of them names.

    The offer's own list is data we trust more than a small model's reading of the text:
    v2 with qwen2.5:3b left out Django, Git and SQL of an offer that listed them.
    """
    extra = [
        Requirement(text=technology, required=True)
        for technology in technologies
        if not any(mentions(r.text, technology) for r in requirements)
    ]
    return [*requirements, *extra]


def match_skills(
    requirements: list[Requirement], user_skills: list[str], resume_text: str | None = None
) -> tuple[list[str], list[str]]:
    """(matched, missing): the user's skills the posting asks for, in the user's spelling,
    and the required skills none of them covers, as the posting words them. Traits,
    experience, languages and education are in neither list."""
    by_key = {skill.strip().lower(): skill for skill in user_skills}
    matched: list[str] = []
    missing: list[str] = []
    for requirement in skill_requirements(requirements):
        skill = covering_skill(requirement, by_key, resume_text)
        if skill is not None:
            matched.append(skill)
        elif requirement.required:
            missing.append(requirement.text)
    return unique_ignoring_case(matched), unique_ignoring_case(missing)


def share_points(
    requirements: list[Requirement], by_key: dict[str, str], points: int, resume_text: str | None
) -> int:
    """points x the share of these requirements the user covers, rounded."""
    covered = sum(covering_skill(r, by_key, resume_text) is not None for r in requirements)
    return round(points * covered / len(requirements))


def skill_points(
    requirements: list[Requirement], user_skills: list[str], resume_text: str | None = None
) -> tuple[int, int]:
    """(required points, nice-to-have points), counting only skills.

    No required skills found: half the points, we can't tell. No nice-to-haves: all
    of them, since there is nothing to miss.
    """
    by_key = {skill.strip().lower(): skill for skill in user_skills}
    skills = skill_requirements(requirements)
    required = [r for r in skills if r.required]
    nice = [r for r in skills if not r.required]
    required_points = (
        share_points(required, by_key, REQUIRED_POINTS, resume_text)
        if required
        else REQUIRED_POINTS // 2
    )
    nice_points = (
        share_points(nice, by_key, NICE_TO_HAVE_POINTS, resume_text)
        if nice
        else NICE_TO_HAVE_POINTS
    )
    return required_points, nice_points


def level_points(offer_level: ExperienceLevel | None, user_level: ExperienceLevel | None) -> int:
    """Same level 20, one step apart 10, further 0; 10 if either is unknown."""
    if offer_level is None or user_level is None:
        return LEVEL_POINTS // 2
    steps = abs(LADDER.index(offer_level) - LADDER.index(user_level))
    if steps == 0:
        return LEVEL_POINTS
    return LEVEL_POINTS // 2 if steps == 1 else 0


def location_points(location: str | None, preferred: list[str]) -> int:
    """In a preferred city (any spelling) or remote 10; 5 if either side is unknown; else 0."""
    if not location or not location.strip():
        return LOCATION_POINTS // 2
    if is_remote(location):
        return LOCATION_POINTS
    if not preferred:
        return LOCATION_POINTS // 2
    asked = {city_key(place) for place in preferred if not is_remote(place)}
    if any(city in asked for city in cities_in(location)):
        return LOCATION_POINTS
    words = f' {normalize(location)} '
    if any(f' {normalize(key)} ' in words for key in asked):  # a city we don't list
        return LOCATION_POINTS
    return 0


def employment_type_points(
    offer_type: EmploymentType | None, preferred: list[EmploymentType]
) -> int:
    """One of the preferred types 5, unknown 3, else 0."""
    if offer_type is None or not preferred:
        return 3
    return EMPLOYMENT_TYPE_POINTS if offer_type in preferred else 0


def score_breakdown(
    offer: JobOfferImport,
    profile: ProfileRead,
    output: OfferAnalysisOutput,
    resume_text: str | None = None,
) -> ScoreBreakdown:
    requirements = with_offer_technologies(output.requirements, offer.technologies)
    required, nice = skill_points(requirements, profile.skills, resume_text)
    return ScoreBreakdown(
        required_skills=required,
        nice_to_have_skills=nice,
        experience_level=level_points(offer_level(offer), profile.experience_level),
        location=location_points(offer.location, profile.preferred_locations),
        employment_type=employment_type_points(
            offer.employment_type, profile.preferred_employment_types
        ),
        role_fit=output.role_fit,
    )


def score(offer: JobOfferImport, profile: ProfileRead, output: OfferAnalysisOutput) -> int:
    """The rubric total, 0-100."""
    return score_breakdown(offer, profile, output).total


def offer_level(offer: JobOfferImport) -> ExperienceLevel | None:
    return offer.experience_level or guess_level(offer.title, offer.description)


def facts_text(
    offer: JobOfferImport,
    profile: ProfileRead,
    requirements: list[Requirement],
    resume_text: str | None = None,
) -> str:
    """What code knows for sure, as plain lines for step 2: the model only judges it."""
    by_key = {skill.strip().lower(): skill for skill in profile.skills}
    covered: list[str] = []
    lacks: list[str] = []
    lacks_nice: list[str] = []
    for r in skill_requirements(requirements):
        skill = covering_skill(r, by_key, resume_text)
        if skill is not None:
            covered.append(r.text if skill.lower() == r.text.lower() else f'{r.text} ({skill})')
        else:
            (lacks if r.required else lacks_nice).append(r.text)
    other = [
        f'{r.text} ({r.kind}{"" if r.required else ", optional"})'
        for r in requirements
        if r.kind not in (RequirementKind.SKILL, RequirementKind.TRAIT)
    ]

    def listed(items: list[str]) -> str:
        return ', '.join(unique_ignoring_case(items)) or 'none'

    level = offer_level(offer)
    lines = [
        f'Skills the candidate covers: {listed(covered)}',
        f'Required skills the candidate lacks: {listed(lacks)}',
        f'Nice-to-have skills the candidate lacks: {listed(lacks_nice)}',
        f'Other demands of the posting: {listed(other)}',
        f'Offer level: {level or "not given"}; '
        f'candidate level: {profile.experience_level or "not given"}',
        f'Location: {offer.location or "not given"} '
        f'({location_verdict(location_points(offer.location, profile.preferred_locations))})',
        f'Employment type: {offer.employment_type or "not given"} ('
        + employment_verdict(
            employment_type_points(offer.employment_type, profile.preferred_employment_types)
        )
        + ')',
    ]
    return '\n'.join(lines)


def location_verdict(points: int) -> str:
    if points == LOCATION_POINTS:
        return "fits the candidate's preferences"
    return 'unknown fit' if points else "not one of the candidate's places"


def employment_verdict(points: int) -> str:
    if points == EMPLOYMENT_TYPE_POINTS:
        return "one of the candidate's preferred types"
    return 'unknown fit' if points else "not one of the candidate's preferred types"


def consistent_red_flags(red_flags: list[str], reasons: list[str], covered: list[str]) -> list[str]:
    """Red flags without contradictions: none that names a skill the user covers ('SQL might
    be too much for a junior' while SQL is matched) or repeats a reason word for word."""
    said = {reason.casefold() for reason in reasons}
    return [
        flag
        for flag in red_flags
        if flag.casefold() not in said and not any(mentions(flag, skill) for skill in covered)
    ]


def analyse(
    provider: AIProvider,
    offer: JobOfferImport,
    profile: ProfileRead,
    resume_text: str | None = None,
) -> AnalysisResult:
    """Ask the model about the offer in two steps, then score it with the rubric.

    The CV text, when given, is extra evidence: step 2 reads it, and a skill the posting asks
    for that the CV names counts as covered.
    Raises AIProviderError or AIOutputError like every AI call.
    """
    found = generate(provider, offer_requirements_messages(offer, profile), OfferRequirementsOutput)
    requirements = with_offer_technologies(found.requirements, offer.technologies)
    facts = facts_text(offer, profile, requirements, resume_text)
    judgement = generate(
        provider,
        offer_judgement_messages(offer, profile, facts, resume_text),
        OfferJudgementOutput,
    )
    output = OfferAnalysisOutput(requirements=requirements, **judgement.model_dump())
    matched, missing = match_skills(requirements, profile.skills, resume_text)
    breakdown = score_breakdown(offer, profile, output, resume_text)
    return AnalysisResult(
        score=breakdown.total,
        breakdown=breakdown,
        summary=judgement.summary,
        reasons=judgement.reasons,
        red_flags=consistent_red_flags(judgement.red_flags, judgement.reasons, matched),
        matched_skills=matched,
        missing_skills=missing,
        provider=provider.name,
        model=provider.model,
        prompt_version=OFFER_ANALYSIS_VERSION,
    )
