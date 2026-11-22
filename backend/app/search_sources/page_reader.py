"""Read the text of one web page, e.g. the full posting behind a search result."""

from abc import ABC, abstractmethod
from typing import override

import httpx
from pydantic import SecretStr

TAVILY_EXTRACT_URL = 'https://api.tavily.com/extract'
TIMEOUT_SECONDS = 15


class PageReader(ABC):
    @abstractmethod
    def read(self, url: str) -> str | None:
        """The page's text, or None if it can't be read. Never raises: a page we can't
        read only means less data, never a failed request."""


class TavilyPageReader(PageReader):
    """Tavily Extract: same key as Tavily search; 1 credit per 5 pages read."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)  # tests pass their own

    @override
    def read(self, url: str) -> str | None:
        try:
            response = self.client.post(
                TAVILY_EXTRACT_URL,
                json={'urls': [url], 'extract_depth': 'basic', 'format': 'text'},
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            text = response.json()['results'][0]['raw_content']
        # down, timeout, error status, not JSON, or the page is in failed_results
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            return None
        if not isinstance(text, str) or not text.strip():
            return None
        return text.strip()


class FakePageReader(PageReader):
    """For tests: answers from a dict of pages, None for any other link."""

    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.pages = pages or {}
        self.urls: list[str] = []

    @override
    def read(self, url: str) -> str | None:
        self.urls.append(url)
        return self.pages.get(url)


def build_page_reader(tavily_api_key: SecretStr | None) -> PageReader | None:
    """Tavily Extract when there is a Tavily key, otherwise None (results keep their snippet)."""
    if tavily_api_key is None or not tavily_api_key.get_secret_value():
        return None
    return TavilyPageReader(tavily_api_key.get_secret_value())
