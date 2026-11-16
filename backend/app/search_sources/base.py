from abc import ABC, abstractmethod

from app.schemas.job_offer import JobOfferImport
from app.schemas.search import SearchQuery


class SearchSourceError(Exception):
    """A search API failed: timeout, wrong key, or a response we can't read."""


class SearchSource(ABC):
    """One place we can search for job offers (Tavily, JSearch, a fake in tests)."""

    name: str  # short id shown to the user and saved as found_via, e.g. 'tavily'

    @abstractmethod
    def search(self, query: SearchQuery, limit: int) -> list[JobOfferImport]:
        """Return at most `limit` offers for the query; raise SearchSourceError on failure."""

    @abstractmethod
    def test(self) -> bool:
        """Return True if the source works (key valid, API reachable). Never raises."""
