"""Summaries of job postings: made by the AI on request and kept on the offer.

A summary doesn't depend on who asks (no profile goes into it), so an offer has one, shared
by everyone who can see the offer. Asking again replaces it, e.g. after a better prompt.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.prompts import OFFER_SUMMARY_VERSION, offer_summary_messages
from app.ai.structured import generate
from app.models import JobOffer
from app.schemas.ai import OfferSummary, OfferSummaryRead
from app.services.ai_analysis import get_visible_offer, offer_as_import
from app.services.offer_parsing import provider_label

# Shorter than this is a title or a one-line note, not a posting worth summarising
MIN_DESCRIPTION_CHARS = 100


class NoDescriptionError(Exception):
    """The offer has no description (or only a line), so there is nothing to summarise."""


def summarise_offer(
    db: Session, provider: AIProvider, user_id: int, offer_id: int
) -> OfferSummaryRead:
    """Summarise an offer the user can see and keep the summary on the offer.

    Raises OfferNotFoundError, NoDescriptionError, or the AI errors (AIProviderError,
    AIOutputError); on an AI error the old summary, if any, stays.
    """
    offer = get_visible_offer(db, offer_id, user_id)
    if len((offer.description or '').strip()) < MIN_DESCRIPTION_CHARS:
        raise NoDescriptionError

    summary = generate(provider, offer_summary_messages(offer_as_import(offer)), OfferSummary)
    stored = summary.model_dump(mode='json')
    now = datetime.now(UTC)
    offer.summary = stored
    offer.summary_with = provider_label(provider)
    offer.summary_prompt_version = OFFER_SUMMARY_VERSION
    offer.summarized_at = now
    db.commit()
    return read_stored(offer, stored, now)


def get_summary(db: Session, user_id: int, offer_id: int) -> OfferSummaryRead | None:
    """The offer's summary, None if it has none yet. OfferNotFoundError if the user can't
    see the offer."""
    return to_summary_read(get_visible_offer(db, offer_id, user_id))


def to_summary_read(offer: JobOffer) -> OfferSummaryRead | None:
    if offer.summary is None or offer.summarized_at is None:
        return None
    return read_stored(offer, offer.summary, offer.summarized_at)


def read_stored(offer: JobOffer, summary: dict[str, Any], created_at: datetime) -> OfferSummaryRead:
    """The stored JSON with what made it. Read through OfferSummary again, so a summary
    stored by an older prompt still fits (unknown fields are ignored)."""
    return OfferSummaryRead.model_validate(
        {
            **summary,
            'job_offer_id': offer.id,
            'summary_with': offer.summary_with or 'unknown',
            'prompt_version': offer.summary_prompt_version or 'unknown',
            'created_at': created_at,
        }
    )
