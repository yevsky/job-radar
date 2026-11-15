"""Fill the database with the demo offers "posted" on JobRadar (run with `just seed`)."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.db.session import SessionLocal
from app.models.enums import SourceKind
from app.schemas.job_offer import ImportReport
from app.services.job_offer_import import import_offers, parse_json_rows

SEED_FILE = BASE_DIR / 'seed' / 'job_offers.json'


def seed_offers(db: Session, path: Path = SEED_FILE) -> ImportReport:
    """Import the demo offers from the seed file as posted offers."""
    rows = parse_json_rows(path.read_bytes())
    return import_offers(db, rows, SourceKind.POSTED)


def main() -> None:
    with SessionLocal() as db:
        report = seed_offers(db)
    print(f'created: {report.created}, updated: {report.updated}, skipped: {report.skipped}')
    for error in report.errors:
        print(f'row {error.row}: {error.message}')


if __name__ == '__main__':
    main()
