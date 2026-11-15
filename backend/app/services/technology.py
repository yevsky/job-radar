from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Technology


def get_or_create_technologies(db: Session, names: list[str]) -> list[Technology]:
    """Return a Technology for each name, reusing existing rows regardless of letter case."""
    if not names:
        return []
    lowered = [name.lower() for name in names]
    existing = db.scalars(select(Technology).where(func.lower(Technology.name).in_(lowered))).all()
    by_key = {tech.name.lower(): tech for tech in existing}

    technologies = []
    for name in names:
        tech = by_key.get(name.lower())
        if tech is None:
            tech = Technology(name=name)
            db.add(tech)
            by_key[name.lower()] = tech
        technologies.append(tech)

    db.flush()
    return technologies
