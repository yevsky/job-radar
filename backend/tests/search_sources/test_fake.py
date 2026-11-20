import pytest
from pydantic import ValidationError

from app.models.enums import ExperienceLevel
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import PostedWithin, SearchQuery
from app.search_sources.base import SearchSource, SearchSourceError
from app.search_sources.fake import FakeSearchSource


def make_result(number: int) -> JobOfferImport:
    return JobOfferImport.model_validate(
        {
            'title': f'Backend Developer {number}',
            'company_name': 'Codesky',
            'url': f'https://example.com/jobs/{number}',
        }
    )


QUERY = SearchQuery(position='Python developer')


# SearchQuery.text()


def test_text_joins_position_and_cities() -> None:
    query = SearchQuery(position='Junior Python developer', locations=['Wrocław', 'Remote'])
    assert query.text() == 'Junior Python developer Wrocław OR Remote'


def test_text_skips_empty_parts() -> None:
    query = SearchQuery(position=' Python ', locations=['', ' '])
    assert query.text() == 'Python'


def test_text_with_one_location_has_no_or() -> None:
    query = SearchQuery(position='Tester', locations=['Kraków'])
    assert query.text() == 'Tester Kraków'


def test_text_of_empty_query_is_empty() -> None:
    assert SearchQuery().text() == ''


def test_filters_are_not_in_the_phrase() -> None:
    query = SearchQuery(position='Tester', country='de', posted_within=PostedWithin.WEEK, page=2)
    assert query.text() == 'Tester'


def test_country_defaults_to_the_setting_and_is_lowercased() -> None:
    assert SearchQuery().country == 'pl'
    assert SearchQuery(country=' DE ').country == 'de'


def test_old_fields_are_ignored() -> None:
    """An older frontend may still send skills or a level; they don't fail the search."""
    query = SearchQuery.model_validate(
        {'position': 'Tester', 'skills': ['Python'], 'experience_level': 'junior'}
    )
    assert query.text() == 'Tester'
    assert query.wanted_level() is None


@pytest.mark.parametrize(
    ('fields', 'empty'),
    [
        ({}, True),
        ({'position': '  ', 'locations': ['Wrocław']}, True),
        ({'position': 'Tester'}, False),
    ],
)
def test_is_empty(fields: dict[str, object], empty: bool) -> None:
    assert SearchQuery.model_validate(fields).is_empty() is empty


@pytest.mark.parametrize(
    'fields',
    [
        {'position': 'x' * 121},
        {'locations': [f'city {n}' for n in range(6)]},
        {'locations': ['x' * 101]},
        {'posted_within': 'year'},
        {'country': 'poland'},
        {'page': 0},
        {'page': 11},
    ],
)
def test_query_rejects_wrong_input(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchQuery.model_validate(fields)


# FakeSearchSource


def test_fake_returns_its_results() -> None:
    results = [make_result(1), make_result(2)]
    source = FakeSearchSource(results=results)
    page = source.search(QUERY, limit=10)
    assert page.offers == results
    assert page.has_more is False


def test_fake_respects_limit_and_has_more() -> None:
    source = FakeSearchSource(results=[make_result(n) for n in range(5)])
    page = source.search(QUERY, limit=2)
    assert len(page.offers) == 2
    assert page.has_more is True


def test_fake_returns_the_asked_page() -> None:
    source = FakeSearchSource(results=[make_result(n) for n in range(5)])

    second = source.search(QUERY.model_copy(update={'page': 2}), limit=2)
    third = source.search(QUERY.model_copy(update={'page': 3}), limit=2)
    fourth = source.search(QUERY.model_copy(update={'page': 4}), limit=2)

    assert [o.title for o in second.offers] == ['Backend Developer 2', 'Backend Developer 3']
    assert second.has_more is True
    assert [o.title for o in third.offers] == ['Backend Developer 4']
    assert third.has_more is False
    assert fourth.offers == []


def test_fake_uses_no_filters() -> None:
    assert FakeSearchSource().features == frozenset()


def test_fake_records_queries() -> None:
    source = FakeSearchSource()
    other = SearchQuery(position='Java developer')
    source.search(QUERY, limit=10)
    source.search(other, limit=10)
    assert source.queries == [QUERY, other]


def test_fake_without_results_returns_empty_list() -> None:
    assert FakeSearchSource().search(QUERY, limit=10).offers == []


def test_failing_fake_raises_and_still_records_query() -> None:
    source = FakeSearchSource(name='broken', fail=True)
    with pytest.raises(SearchSourceError, match='broken'):
        source.search(QUERY, limit=10)
    assert source.queries == [QUERY]


def test_test_method_reports_health() -> None:
    assert FakeSearchSource().test() is True
    assert FakeSearchSource(fail=True).test() is False


def test_name_defaults_to_fake() -> None:
    assert FakeSearchSource().name == 'fake'
    assert FakeSearchSource(name='tavily').name == 'tavily'


def test_fake_is_a_search_source() -> None:
    source: SearchSource = FakeSearchSource()  # mypy checks this line too
    assert isinstance(source, SearchSource)


def test_interface_cannot_be_used_directly() -> None:
    with pytest.raises(TypeError):
        SearchSource()  # type: ignore[abstract]


# SearchQuery.wanted_level() and levels in the phrase


def test_level_word_in_position_is_the_wanted_level() -> None:
    query = SearchQuery(position='Junior Python developer', locations=['Kraków'])

    assert query.wanted_level() == ExperienceLevel.JUNIOR
    assert query.text() == 'Junior Python developer Kraków'  # the position is sent as written


def test_no_level_anywhere_means_no_wanted_level() -> None:
    assert SearchQuery(position='Python developer').wanted_level() is None
