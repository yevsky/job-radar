from app.schemas.job_offer import JobOfferImport
from app.schemas.search import SearchQuery
from app.search_sources.base import SearchSource, SearchSourceError


class FakeSearchSource(SearchSource):
    """A search source with fixed results, for tests and for working without API keys."""

    def __init__(
        self,
        name: str = 'fake',
        results: list[JobOfferImport] | None = None,
        fail: bool = False,
    ) -> None:
        self.name = name
        self.results = results or []
        self.fail = fail
        self.queries: list[SearchQuery] = []  # every query received, so tests can check it

    def search(self, query: SearchQuery, limit: int) -> list[JobOfferImport]:
        self.queries.append(query)
        if self.fail:
            raise SearchSourceError(f'{self.name} is set to fail')
        return self.results[:limit]

    def test(self) -> bool:
        return not self.fail
