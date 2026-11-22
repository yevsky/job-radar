from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas.job_offer import JobOfferImport
from app.schemas.search import HiddenReason, SearchQuery, SourceFeature


class SearchSourceError(Exception):
    """A search API failed: timeout, wrong key, or a response we can't read."""


@dataclass
class HiddenOffer:
    """An offer the source read but left out, and why."""

    offer: JobOfferImport
    reason: HiddenReason


@dataclass
class SourcePage:
    """One page of a source's answer, and whether asking for the next page may find more."""

    offers: list[JobOfferImport] = field(default_factory=list)
    has_more: bool = False
    hidden: list[HiddenOffer] = field(default_factory=list)  # read, but left out on purpose
    skipped: int = 0  # rows the source got but couldn't read (no title, a broken link)


class SearchSource(ABC):
    """One place we can search for job offers (Tavily, JSearch, a fake in tests)."""

    name: str  # short id shown to the user and saved as found_via, e.g. 'tavily'
    # the form fields this source uses besides position and cities (see SourceFeature)
    features: frozenset[SourceFeature] = frozenset()

    @abstractmethod
    def search(self, query: SearchQuery, limit: int) -> SourcePage:
        """Return page `query.page` of at most `limit` offers; raise SearchSourceError."""

    @abstractmethod
    def test(self) -> bool:
        """Return True if the source works (key valid, API reachable). Never raises."""
