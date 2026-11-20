"""Cities and countries in free text: the search form, offer locations and offer links."""

import re
import unicodedata

# Polish cities job boards list most, as (name shown to the user, other spellings).
# Spellings are written without diacritics, because text is compared that way.
CITIES: list[tuple[str, list[str]]] = [
    ('Warszawa', ['warszawa', 'warsaw', 'warschau', 'varsovie']),
    ('Kraków', ['krakow', 'cracow', 'krakau']),
    ('Wrocław', ['wroclaw', 'breslau']),
    ('Gdańsk', ['gdansk', 'danzig']),
    ('Gdynia', ['gdynia']),
    ('Sopot', ['sopot']),
    ('Trójmiasto', ['trojmiasto', 'tricity']),
    ('Poznań', ['poznan']),
    ('Łódź', ['lodz']),
    ('Katowice', ['katowice']),
    ('Gliwice', ['gliwice']),
    ('Szczecin', ['szczecin']),
    ('Lublin', ['lublin']),
    ('Białystok', ['bialystok']),
    ('Bydgoszcz', ['bydgoszcz']),
    ('Toruń', ['torun']),
    ('Rzeszów', ['rzeszow']),
    ('Olsztyn', ['olsztyn']),
    ('Kielce', ['kielce']),
    ('Opole', ['opole']),
    ('Częstochowa', ['czestochowa']),
    ('Radom', ['radom']),
    ('Bielsko-Biała', ['bielsko biala']),
    ('Zielona Góra', ['zielona gora']),
]

# Words that mean the job is done from home.
REMOTE_WORDS = ['remote', 'zdalnie', 'zdalna', 'praca zdalna', 'home office', 'work from home']

# ISO codes of the countries the search form offers -> the English names Tavily expects.
COUNTRIES = {
    'pl': 'poland',
    'de': 'germany',
    'gb': 'united kingdom',
    'nl': 'netherlands',
    'cz': 'czech republic',
    'us': 'united states',
}


def normalize(text: str) -> str:
    """Lowercase words without diacritics or punctuation: 'Wrocław, Dolnośląskie' -> 'wroclaw
    dolnoslaskie'. Links work too: 'python-dev-warszawa' -> 'python dev warszawa'."""
    text = text.casefold().replace('ł', 'l')  # NFKD doesn't split ł into l + a mark
    text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def contains(text: str, phrase: str) -> bool:
    """True if the normalized text has the normalized phrase as whole words."""
    return bool(phrase) and f' {phrase} ' in f' {text} '


def cities_in(text: str) -> list[str]:
    """The known cities named in the text, by their shown name, in the order of CITIES."""
    words = normalize(text)
    return [name for name, spellings in CITIES if any(contains(words, s) for s in spellings)]


def is_remote(text: str) -> bool:
    words = normalize(text)
    return any(contains(words, word) for word in REMOTE_WORDS)


def city_key(city: str) -> str:
    """One key for every spelling of a city: 'Warsaw' and 'Warszawa' -> 'Warszawa'.

    A city we don't know is its own key: 'Lisbon' -> 'lisbon'.
    """
    found = cities_in(city)
    return found[0] if found else normalize(city)


def guess_location(*texts: str, wanted: list[str] | None = None) -> str | None:
    """A location from texts that aren't one (a link, a page title); None if none is named.

    Cities the user asked for are looked for too, so 'Lisbon' is found even though it isn't
    in CITIES. 'Remote' is returned only when no city is named.
    """
    for text in texts:
        found = cities_in(text)
        if found:
            return found[0]
        words = normalize(text)
        for city in wanted or []:
            if not is_remote(city) and contains(words, normalize(city)):
                return city
    if any(is_remote(text) for text in texts):
        return 'Remote'
    return None


def location_fits(location: str | None, wanted: list[str]) -> bool:
    """Should an offer in `location` be shown to someone who asked for `wanted` places?

    - Nothing asked for, or the offer's location is unknown: kept (better one extra result
      than hiding a good one).
    - The offer names an asked city in any spelling ('Warsaw' fits 'Warszawa'): kept.
    - A remote offer: kept only if 'Remote' was asked for.
    - The offer names a different known city ('Katowice' for 'Warszawa'): left out.
    - Anything else ('Poland', 'Mazowieckie'): kept, we can't tell.
    """
    if not wanted or not location or not location.strip():
        return True
    words = normalize(location)
    wants_remote = any(is_remote(place) for place in wanted)
    asked = {city_key(place) for place in wanted if not is_remote(place)}

    named = cities_in(location)
    if any(city in asked for city in named):
        return True
    if any(contains(words, normalize(key)) for key in asked):  # a city we don't list
        return True
    if is_remote(location):
        return wants_remote
    return not named


def country_name(code: str | None) -> str | None:
    """The English name of an ISO country code, e.g. 'pl' -> 'poland'; None if unknown."""
    return COUNTRIES.get((code or '').lower())
