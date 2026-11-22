"""Read job postings with the AI: a pasted posting, or the page behind a saved search result."""

import logging
import re
from datetime import UTC, datetime, time
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError
from app.ai.prompts import offer_parse_messages
from app.ai.structured import AIOutputError, generate
from app.models import JobOffer
from app.schemas.ai import (
    MAX_POSTING_TEXT,
    JobOfferParseRequest,
    JobOfferParseResponse,
    ParsedOffer,
)
from app.search_sources.page_reader import PageReader
from app.services.technology import get_or_create_technologies

logger = logging.getLogger(__name__)

# A web link inside pasted text: up to the first space, quote or bracket.
LINK_PATTERN = re.compile(r'https?://[^\s<>"\'()\[\]{}]+', re.IGNORECASE)
# Punctuation that ends a sentence, not the link: "Apply at https://x.pl/job."
LINK_TRAILING = '.,;:!?'
MAX_LINK_LENGTH = 2048


def parse_offer(provider: AIProvider, text: str) -> ParsedOffer:
    """The posting's fields, read by the model. Raises AIProviderError or AIOutputError."""
    return generate(provider, offer_parse_messages(text), ParsedOffer)


def provider_label(provider: AIProvider) -> str:
    """'ollama/qwen2.5:3b': which provider and model produced a result."""
    return f'{provider.name}/{provider.model}'


def find_link(text: str) -> str | None:
    """The first web link in the text, or None. Found by code, not by the AI.

    A pasted posting often ends with "Apply: https://...", and a small model can invent or
    cut a link, so we never ask it for one.
    """
    for match in LINK_PATTERN.finditer(text):
        link = match.group().rstrip(LINK_TRAILING)
        if len(link) <= MAX_LINK_LENGTH and '.' in (urlsplit(link).hostname or ''):
            return link
    return None


def draft_offer(provider: AIProvider, data: JobOfferParseRequest) -> JobOfferParseResponse:
    """A pasted posting turned into a draft offer for the user to check. Saves nothing.

    The link is the one the user gave; without one, the first link in the text.
    """
    parsed = parse_offer(provider, data.text)
    return JobOfferParseResponse(
        **parsed.model_dump(),
        url=str(data.url) if data.url else find_link(data.text),
        description=data.text,
        parsed_with=provider_label(provider),
    )


def fill_empty_fields(
    db: Session, offer: JobOffer, parsed: ParsedOffer, page_text: str | None
) -> None:
    """Copy parsed fields onto the offer, but only where the offer has nothing yet.

    Whatever the search source gave stays: it read structured data, the model only guesses.
    Title and company are never touched; they are required, so the source always gave them.
    """
    if offer.location is None:
        offer.location = parsed.location
    if offer.experience_level is None:
        offer.experience_level = parsed.experience_level
    if offer.employment_type is None:
        offer.employment_type = parsed.employment_type
    if offer.deadline is None and parsed.deadline is not None:
        offer.deadline = datetime.combine(parsed.deadline, time(), tzinfo=UTC)
    if not offer.technologies:
        offer.technologies = get_or_create_technologies(db, parsed.technologies)
    if not offer.description and page_text:
        offer.description = page_text[:MAX_POSTING_TEXT]


def enrich_saved_offer(
    db: Session, offer: JobOffer, provider: AIProvider, reader: PageReader | None
) -> bool:
    """Fill a just-saved search result from its full page; True if the AI's fields were used.

    Reads the page (falls back to the result's own description), parses it and fills the
    empty fields. Any failure is only logged: the offer is already saved and stays as it was.
    """
    page_text = reader.read(offer.url) if reader is not None else None
    text = page_text or offer.description
    if not text:
        return False
    try:
        parsed = parse_offer(provider, text)
    except (AIProviderError, AIOutputError) as err:
        logger.warning('Could not fill offer %s with AI: %s', offer.id, err)
        return False

    fill_empty_fields(db, offer, parsed, page_text)
    db.commit()
    return True
