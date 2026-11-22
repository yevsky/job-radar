"""Run match analyses for the API: offers from the database (stored) and search results (not).

The scoring itself is in services/analysis.py; this module only finds the inputs (offer,
profile, CV text) for one user and stores the result.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.models import AiAnalysis, JobOffer, User
from app.schemas.analysis import AnalysisResult
from app.schemas.job_offer import JobOfferImport
from app.schemas.profile import ProfileRead
from app.schemas.search import SearchResult
from app.services.analysis import analyse
from app.services.job_offer import OfferNotFoundError, visible_to
from app.services.profile import to_profile_read
from app.services.resume import get_resume


class EmptyProfileError(Exception):
    """The profile has neither a desired position nor a skill, so there is nothing to match."""


def profile_for_analysis(user: User) -> ProfileRead:
    """The user's profile, or EmptyProfileError if a match would be meaningless."""
    profile = to_profile_read(user)
    if not profile.desired_position and not profile.skills:
        raise EmptyProfileError
    return profile


def resume_text(db: Session, user_id: int, resume_id: int | None) -> str | None:
    """The text of the user's CV, None without one; another user's CV is ResumeNotFoundError."""
    if resume_id is None:
        return None
    return get_resume(db, user_id, resume_id).text


def offer_as_import(offer: JobOffer) -> JobOfferImport:
    """A database offer in the shape the analysis reads (the same as a search result's)."""
    return JobOfferImport.model_validate(
        {
            'title': offer.title,
            'company_name': offer.company_name,
            'url': offer.url,
            'location': offer.location,
            'experience_level': offer.experience_level,
            'employment_type': offer.employment_type,
            'deadline': offer.deadline,
            'technologies': [t.name for t in offer.technologies],
            'description': offer.description,
        }
    )


def get_visible_offer(db: Session, offer_id: int, user_id: int) -> JobOffer:
    offer = db.scalar(select(JobOffer).where(JobOffer.id == offer_id, visible_to(user_id)))
    if offer is None:
        raise OfferNotFoundError
    return offer


def analyse_offer(
    db: Session, provider: AIProvider, user: User, offer_id: int, resume_id: int | None
) -> AiAnalysis:
    """Analyse an offer the user can see and store the result as a new row.

    Checks run before the (slow) AI call: offer, then CV, then profile.
    Raises OfferNotFoundError, ResumeNotFoundError, EmptyProfileError, or the AI errors.
    """
    offer = get_visible_offer(db, offer_id, user.id)
    cv_text = resume_text(db, user.id, resume_id)
    profile = profile_for_analysis(user)

    result = analyse(provider, offer_as_import(offer), profile, cv_text)

    row = AiAnalysis(
        user_id=user.id,
        job_offer_id=offer.id,
        resume_id=resume_id,
        **result.model_dump(exclude={'breakdown'}),
        breakdown=result.breakdown.model_dump(),
    )
    db.add(row)
    db.commit()
    return row


def latest_analysis(db: Session, user_id: int, offer_id: int) -> AiAnalysis | None:
    """The user's newest analysis of the offer; other users' analyses are never returned."""
    get_visible_offer(db, offer_id, user_id)
    return db.scalar(
        select(AiAnalysis)
        .where(AiAnalysis.user_id == user_id, AiAnalysis.job_offer_id == offer_id)
        .order_by(AiAnalysis.created_at.desc(), AiAnalysis.id.desc())
        .limit(1)
    )


def analyse_search_result(
    db: Session, provider: AIProvider, user: User, result: SearchResult, resume_id: int | None
) -> AnalysisResult:
    """Analyse a search result without storing anything (search results aren't stored)."""
    cv_text = resume_text(db, user.id, resume_id)
    profile = profile_for_analysis(user)
    return analyse(provider, result, profile, cv_text)
