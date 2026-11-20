import pytest

from app.core.locations import (
    cities_in,
    city_key,
    country_name,
    guess_location,
    location_fits,
    normalize,
)


def test_normalize_drops_diacritics_and_punctuation() -> None:
    assert normalize('Wrocław, Dolnośląskie') == 'wroclaw dolnoslaskie'
    assert normalize('ŁÓDŹ') == 'lodz'
    assert normalize('python-dev-warszawa') == 'python dev warszawa'


@pytest.mark.parametrize(
    ('text', 'cities'),
    [
        ('Warsaw, Masovian Voivodeship, Poland', ['Warszawa']),
        ('Krakow', ['Kraków']),
        ('Cracow / Wroclaw', ['Kraków', 'Wrocław']),
        ('Bielsko-Biała', ['Bielsko-Biała']),
        ('Radomsko', []),  # a whole word only: Radomsko is not Radom
        ('Poland', []),
    ],
)
def test_cities_in(text: str, cities: list[str]) -> None:
    assert cities_in(text) == cities


def test_city_key_joins_spellings() -> None:
    assert city_key('Warsaw') == city_key('warszawa') == 'Warszawa'
    assert city_key('Lisbon') == 'lisbon'


@pytest.mark.parametrize(
    ('location', 'wanted', 'fits'),
    [
        ('Katowice, Śląskie, Poland', ['Warsaw', 'Wrocław'], False),
        ('Warszawa, Mazowieckie, Poland', ['Warsaw'], True),
        ('Wroclaw (remote)', ['Wrocław'], True),
        ('Remote', ['Warsaw'], False),
        ('Poland (remote)', ['Warsaw'], False),
        ('Remote', ['Warsaw', 'Remote'], True),
        ('Poland', ['Warsaw'], True),  # can't tell: kept
        (None, ['Warsaw'], True),
        ('Katowice', [], True),  # nothing asked
        ('Lisbon, Portugal', ['Lisbon'], True),  # a city we don't list
        ('Gdańsk', ['Trójmiasto', 'Gdańsk'], True),
    ],
)
def test_location_fits(location: str | None, wanted: list[str], fits: bool) -> None:
    assert location_fits(location, wanted) is fits


def test_guess_location_prefers_a_city_over_remote() -> None:
    assert guess_location('/job/python-dev-remote-warszawa') == 'Warszawa'
    assert guess_location('/job/python-dev-remote') == 'Remote'
    assert guess_location('/job/42') is None


def test_country_name() -> None:
    assert country_name('PL') == 'poland'
    assert country_name('zz') is None
    assert country_name(None) is None
