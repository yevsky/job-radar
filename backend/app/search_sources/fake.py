import json
from pathlib import Path

from app.core.config import BASE_DIR
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import SearchQuery
from app.search_sources.base import SearchSource, SearchSourceError, SourcePage

DEMO_RESULTS_FILE = BASE_DIR / 'seed' / 'demo_search_results.json'


def load_demo_results(path: Path = DEMO_RESULTS_FILE) -> list[JobOfferImport]:
    """Read the results the 'fake' source returns, so the frontend works without API keys."""
    rows = json.loads(path.read_text(encoding='utf-8'))
    return [JobOfferImport.model_validate(row) for row in rows]


class FakeSearchSource(SearchSource):
    """A search source with fixed results, for tests and for working without API keys.

    It pages its results but uses no other filter, so it has no features.
    """

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

    def search(self, query: SearchQuery, limit: int) -> SourcePage:
        self.queries.append(query)
        if self.fail:
            raise SearchSourceError(f'{self.name} is set to fail')
        start = (query.page - 1) * limit
        return SourcePage(
            offers=self.results[start : start + limit],
            has_more=len(self.results) > start + limit,
        )

    def test(self) -> bool:
        return not self.fail
