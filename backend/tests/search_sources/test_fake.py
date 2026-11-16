import pytest
from pydantic import ValidationError

from app.models.enums import EmploymentType, ExperienceLevel
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


QUERY = SearchQuery(position='Python developer', skills=['FastAPI'])


# SearchQuery.text()


def test_text_joins_all_parts() -> None:
    query = SearchQuery(
        position='Python developer',
        experience_level=ExperienceLevel.JUNIOR,
        skills=['FastAPI', 'PostgreSQL'],
        locations=['Wrocław', 'Remote'],
    )
    assert query.text() == 'junior Python developer FastAPI PostgreSQL Wrocław OR Remote'


def test_text_skips_empty_parts() -> None:
    query = SearchQuery(position='  ', skills=['Python', ' '], locations=[''])
    assert query.text() == 'Python'


def test_text_with_one_location_has_no_or() -> None:
    query = SearchQuery(position='Tester', locations=['Kraków'])
    assert query.text() == 'Tester Kraków'


def test_text_of_empty_query_is_empty() -> None:
    assert SearchQuery().text() == ''


def test_remote_only_adds_remote_once() -> None:
    assert SearchQuery(position='Tester', remote_only=True).text() == 'Tester Remote'
    query = SearchQuery(position='Tester', locations=['remote'], remote_only=True)
    assert query.text() == 'Tester remote'


def test_filters_are_not_in_the_phrase() -> None:
    query = SearchQuery(
        position='Tester',
        employment_types=[EmploymentType.B2B],
        posted_within=PostedWithin.WEEK,
    )
    assert query.text() == 'Tester'


@pytest.mark.parametrize(
    ('fields', 'empty'),
    [
        ({}, True),
        ({'position': '  ', 'skills': [' '], 'locations': ['Wrocław']}, True),
        ({'position': 'Tester'}, False),
        ({'skills': ['Python']}, False),
    ],
)
def test_is_empty(fields: dict[str, object], empty: bool) -> None:
    assert SearchQuery.model_validate(fields).is_empty() is empty


@pytest.mark.parametrize(
    'fields',
    [
        {'position': 'x' * 121},
        {'skills': ['x' * 51]},
        {'skills': [f'skill {n}' for n in range(11)]},
        {'locations': [f'city {n}' for n in range(6)]},
        {'posted_within': 'year'},
        {'employment_types': ['freelance']},
    ],
)
def test_query_rejects_too_long_input(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchQuery.model_validate(fields)


# FakeSearchSource


def test_fake_returns_its_results() -> None:
    results = [make_result(1), make_result(2)]
    source = FakeSearchSource(results=results)
    assert source.search(QUERY, limit=10) == results


def test_fake_respects_limit() -> None:
    source = FakeSearchSource(results=[make_result(n) for n in range(5)])
    assert len(source.search(QUERY, limit=2)) == 2


def test_fake_records_queries() -> None:
    source = FakeSearchSource()
    other = SearchQuery(position='Java developer')
    source.search(QUERY, limit=10)
    source.search(other, limit=10)
    assert source.queries == [QUERY, other]


def test_fake_without_results_returns_empty_list() -> None:
    assert FakeSearchSource().search(QUERY, limit=10) == []


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
