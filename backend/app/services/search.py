from app.models import User
from app.schemas.search import MAX_LOCATIONS, MAX_SKILLS, SearchQuery


def default_search_query(user: User) -> SearchQuery:
    """The search form prefilled from the profile: job fields only, never name, bio or email."""
    profile = user.profile
    return SearchQuery(
        position=profile.desired_position if profile else None,
        experience_level=profile.experience_level if profile else None,
        skills=[technology.name for technology in user.technologies][:MAX_SKILLS],
        locations=[preferred.location for preferred in user.preferred_locations][:MAX_LOCATIONS],
        employment_types=[
            preferred.employment_type for preferred in user.preferred_employment_types
        ],
    )
