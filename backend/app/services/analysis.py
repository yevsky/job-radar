"""Match one offer against the user: the model reads the posting, code decides the score.

The model only maps each requirement to one of the user's skills (or none) and gives a 0-10
role fit, reasons and red flags. Everything else is a fixed rubric in code, so the same
answer always gives the same score and every point can be explained:

    required skills 45 | nice-to-have 10 | level 20 | location 10 | employment type 5 | role fit 10
"""

from app.ai.base import AIProvider
from app.ai.prompts import OFFER_ANALYSIS_VERSION, offer_analysis_messages
from app.ai.structured import generate
from app.core.levels import LADDER, guess_level
from app.core.locations import cities_in, city_key, is_remote, normalize
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import OfferAnalysisOutput, Requirement
from app.schemas.analysis import AnalysisResult, ScoreBreakdown
from app.schemas.job_offer import JobOfferImport
from app.schemas.profile import ProfileRead, unique_ignoring_case

REQUIRED_POINTS = 45
NICE_TO_HAVE_POINTS = 10
LEVEL_POINTS = 20
LOCATION_POINTS = 10
EMPLOYMENT_TYPE_POINTS = 5


def covering_skill(requirement: Requirement, skills_by_key: dict[str, str]) -> str | None:
    """The user's skill the model says covers this requirement, if the user really has it.

    Compared ignoring case and spaces. A skill that isn't in the user's list (the model made
    it up, or took it from the posting) counts as no match.
    """
    if requirement.skill is None:
        return None
    return skills_by_key.get(requirement.skill.strip().lower())


def match_skills(
    requirements: list[Requirement], user_skills: list[str]
) -> tuple[list[str], list[str]]:
    """(matched, missing): the user's skills the posting asks for, in the user's spelling,
    and the required requirements none of them covers, as the posting words them."""
    by_key = {skill.strip().lower(): skill for skill in user_skills}
    matched: list[str] = []
    missing: list[str] = []
    for requirement in requirements:
        skill = covering_skill(requirement, by_key)
        if skill is not None:
            matched.append(skill)
        elif requirement.required:
            missing.append(requirement.text)
    return unique_ignoring_case(matched), unique_ignoring_case(missing)


def share_points(requirements: list[Requirement], by_key: dict[str, str], points: int) -> int:
    """points x the share of these requirements the user covers, rounded."""
    covered = sum(covering_skill(r, by_key) is not None for r in requirements)
    return round(points * covered / len(requirements))


def skill_points(requirements: list[Requirement], user_skills: list[str]) -> tuple[int, int]:
    """(required points, nice-to-have points).

    No required requirements found: half the points, we can't tell. No nice-to-haves: all
    of them, since there is nothing to miss.
    """
    by_key = {skill.strip().lower(): skill for skill in user_skills}
    required = [r for r in requirements if r.required]
    nice = [r for r in requirements if not r.required]
    required_points = (
        share_points(required, by_key, REQUIRED_POINTS) if required else REQUIRED_POINTS // 2
    )
    nice_points = share_points(nice, by_key, NICE_TO_HAVE_POINTS) if nice else NICE_TO_HAVE_POINTS
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
    offer: JobOfferImport, profile: ProfileRead, output: OfferAnalysisOutput
) -> ScoreBreakdown:
    required, nice = skill_points(output.requirements, profile.skills)
    offer_level = offer.experience_level or guess_level(offer.title, offer.description)
    return ScoreBreakdown(
        required_skills=required,
        nice_to_have_skills=nice,
        experience_level=level_points(offer_level, profile.experience_level),
        location=location_points(offer.location, profile.preferred_locations),
        employment_type=employment_type_points(
            offer.employment_type, profile.preferred_employment_types
        ),
        role_fit=output.role_fit,
    )


def score(offer: JobOfferImport, profile: ProfileRead, output: OfferAnalysisOutput) -> int:
    """The rubric total, 0-100."""
    return score_breakdown(offer, profile, output).total


def analyse(
    provider: AIProvider,
    offer: JobOfferImport,
    profile: ProfileRead,
    resume_text: str | None = None,
) -> AnalysisResult:
    """Ask the model about the offer, then score it with the rubric.

    The CV text, when given, is extra evidence for the model (inside <resume> tags), but
    only the profile's skills count as matched: copy CV skills into the profile to count them.
    Raises AIProviderError or AIOutputError like every AI call.
    """
    messages = offer_analysis_messages(offer, profile, resume_text)
    output = generate(provider, messages, OfferAnalysisOutput)
    matched, missing = match_skills(output.requirements, profile.skills)
    breakdown = score_breakdown(offer, profile, output)
    return AnalysisResult(
        score=breakdown.total,
        breakdown=breakdown,
        summary=output.summary,
        reasons=output.reasons,
        red_flags=output.red_flags,
        matched_skills=matched,
        missing_skills=missing,
        provider=provider.name,
        model=provider.model,
        prompt_version=OFFER_ANALYSIS_VERSION,
    )
