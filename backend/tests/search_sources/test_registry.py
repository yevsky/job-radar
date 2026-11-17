import pytest

from app.search_sources.fake import FakeSearchSource, load_demo_results
from app.search_sources.registry import build_sources


def test_build_known_sources() -> None:
    sources = build_sources(['fake'])

    assert len(sources) == 1
    assert isinstance(sources[0], FakeSearchSource)
    assert sources[0].name == 'fake'
    assert sources[0].results == load_demo_results()


def test_no_names_gives_no_sources() -> None:
    assert build_sources([]) == []


def test_unknown_name_raises_with_a_clear_message() -> None:
    with pytest.raises(ValueError, match='Unknown search source.*tavilyy.*Known: fake, tavily'):
        build_sources(['fake', 'tavilyy'])


def test_demo_results_file_is_valid() -> None:
    results = load_demo_results()

    assert len(results) == 8
    urls = [str(result.url) for result in results]
    assert len(set(urls)) == len(urls)  # every demo link is different
    assert all(url.startswith('https://jobradar.local/') for url in urls)
