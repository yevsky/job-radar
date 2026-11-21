import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.validation import format_errors
from app.models import JobOffer
from app.models.enums import SourceKind
from app.schemas.job_offer import ImportReport, ImportRowError, JobOfferImport
from app.services.job_offer import visible_to
from app.services.technology import get_or_create_technologies

TRACKING_PARAMS = {
    'ref',
    'refid',
    'trk',
    'trackingid',
    'gh_src',
    'lever-source',
    'fbclid',
    'gclid',
    'msclkid',
    'src',
}


def is_tracking_param(name: str) -> bool:
    """Return True if a query parameter only records
    where the click came from (utm_*, gclid, ...)."""
    name = name.lower()
    return name.startswith('utm_') or name in TRACKING_PARAMS


def normalize_url(url: str) -> str:
    """Return one canonical spelling of a link, used as the dedup key for job offers.

    Lowercases the scheme and host, drops 'www.', the trailing '/', the '#fragment' and
    tracking parameters, and sorts the remaining query parameters. The path keeps its case.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix('www.')
    path = parts.path.rstrip('/')
    query = sorted(
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not is_tracking_param(name)
    )
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ''))


def fill_offer(db: Session, offer: JobOffer, data: JobOfferImport, now: datetime) -> None:
    """Copy the imported fields onto an offer (new or existing) and mark it as seen now."""
    offer.title = data.title
    offer.company_name = data.company_name
    offer.location = data.location
    offer.employment_type = data.employment_type
    offer.experience_level = data.experience_level
    offer.deadline = data.deadline
    offer.technologies = get_or_create_technologies(db, data.technologies)
    offer.description = data.description
    offer.is_active = True
    offer.last_seen_at = now


def import_offers(db: Session, rows: list[dict[str, Any]], source: SourceKind) -> ImportReport:
    """Save a batch of offers, or update the ones whose normalized URL already exists.

    Each row is validated on its own: an invalid row is reported in errors with its
    1-based number and the other rows still import. A URL repeated within the batch is
    counted as skipped. Existing offers keep their original source, are marked active
    and get a new last_seen_at. Everything is committed once, at the end.
    """
    report = ImportReport()
    seen_urls: set[str] = set()

    for row_number, row in enumerate(rows, start=1):
        try:
            data = JobOfferImport.model_validate(row)
        except ValidationError as err:
            report.errors.append(ImportRowError(row=row_number, message=format_errors(err)))
            continue

        url = normalize_url(str(data.url))
        if url in seen_urls:
            report.skipped += 1
            continue
        seen_urls.add(url)

        offer = db.scalar(select(JobOffer).where(JobOffer.url == url, JobOffer.owner_id.is_(None)))
        if offer is None:
            offer = JobOffer(url=url, source=source)
            db.add(offer)
            report.created += 1
        else:
            report.updated += 1

        fill_offer(db, offer, data, datetime.now(UTC))

    db.commit()
    return report


def add_private_offer(
    db: Session,
    data: JobOfferImport,
    user_id: int,
    source: SourceKind = SourceKind.MANUAL,
    found_via: str | None = None,
) -> tuple[JobOffer, bool]:
    """Save an offer only this user can see; return it and whether it was created.

    If the link is already a public offer, or already in this user's private offers,
    that offer is returned unchanged instead of making a copy.
    """
    url = normalize_url(str(data.url))
    existing = db.scalar(
        select(JobOffer)
        .where(JobOffer.url == url, visible_to(user_id))
        .order_by(JobOffer.owner_id.nulls_first())
        .limit(1)
    )
    if existing is not None:
        return existing, False

    offer = JobOffer(url=url, source=source, found_via=found_via, owner_id=user_id)
    db.add(offer)
    fill_offer(db, offer, data, datetime.now(UTC))
    db.commit()
    return offer, True


class ImportFileError(Exception):
    """The uploaded file can't be read as a list of offers."""


def parse_json_rows(content: bytes) -> list[dict[str, Any]]:
    """Read a JSON file that must contain a list of objects, one per offer."""
    try:
        data = json.loads(content)
    except ValueError as err:  # broken JSON, or bytes that aren't UTF-8 text
        raise ImportFileError('The file is not valid JSON.') from err

    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ImportFileError('The file must contain a JSON list of objects.')
    return data
