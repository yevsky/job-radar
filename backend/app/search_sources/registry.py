from collections.abc import Callable

from app.search_sources.base import SearchSource
from app.search_sources.fake import FakeSearchSource, load_demo_results

# Name in settings -> function that builds the source
SOURCE_FACTORIES: dict[str, Callable[[], SearchSource]] = {
    'fake': lambda: FakeSearchSource(results=load_demo_results()),
}


def build_sources(names: list[str]) -> list[SearchSource]:
    """Build the sources named in settings; raise ValueError for a name we don't know."""
    unknown = [name for name in names if name not in SOURCE_FACTORIES]
    if unknown:
        raise ValueError(
            f'Unknown search source(s) in SEARCH_SOURCES: {", ".join(unknown)}. '
            f'Known: {", ".join(SOURCE_FACTORIES)}'
        )
    return [SOURCE_FACTORIES[name]() for name in names]
