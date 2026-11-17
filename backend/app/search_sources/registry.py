from collections.abc import Callable

from pydantic import SecretStr

from app.core.config import settings
from app.search_sources.base import SearchSource
from app.search_sources.fake import FakeSearchSource, load_demo_results
from app.search_sources.tavily import TavilySource


def require_key(key: SecretStr | None, env_name: str) -> str:
    """The API key's value; raise ValueError at startup if the source is on but has no key."""
    if key is None or not key.get_secret_value().strip():
        raise ValueError(f'{env_name} is empty, but SEARCH_SOURCES turns this source on.')
    return key.get_secret_value()


def build_tavily() -> SearchSource:
    return TavilySource(
        api_key=require_key(settings.tavily_api_key, 'TAVILY_API_KEY'),
        domains=settings.tavily_domains,
    )


# Name in settings -> function that builds the source
SOURCE_FACTORIES: dict[str, Callable[[], SearchSource]] = {
    'fake': lambda: FakeSearchSource(results=load_demo_results()),
    'tavily': build_tavily,
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
