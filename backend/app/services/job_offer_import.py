from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import SourceKind
from app.schemas.job_offer import ImportReport, ImportRowError, JobOfferImport
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


def format_errors(error: ValidationError) -> str:
    """Turn Pydantic's error list into one readable line, e.g. 'title: Field required; url: ...'."""
    return '; '.join(
        f'{".".join(str(part) for part in e["loc"]) or "row"}: {e["msg"]}' for e in error.errors()
    )


def import_offers(db: Session, rows: list[dict[str, Any]], source: SourceKind) -> ImportReport:
    """Save a batch of offers, or update the ones whose normalized URL already exists.

    Each row is validated on its own: an invalid row is reported in errors with its
    1-based number and the other rows still import. A URL repeated within the batch is
    counted as skipped. Existing offers keep their original source, are marked active
    and get a new last_seen_at. Everything is committed once, at the end.
    """
    report = ImportReport()
    now = datetime.now(UTC)
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

        offer = db.scalar(select(JobOffer).where(JobOffer.url == url))
        if offer is None:
            offer = JobOffer(url=url, source=source)
            db.add(offer)
            report.created += 1
        else:
            report.updated += 1

        offer.title = data.title
        offer.company_name = data.company_name
        offer.location = data.location
        offer.employment_type = data.employment_type
        offer.experience_level = data.experience_level
        offer.deadline = data.deadline
        offer.technologies = get_or_create_technologies(db, data.technologies)
        offer.is_active = True
        offer.last_seen_at = now

    db.commit()
    return report
