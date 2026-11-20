"""Show what one search source sends back and what the app keeps, to debug empty results.

Run from backend/:
    uv run python -m app.search_sources.probe tavily "Junior Python developer" Warszawa
It uses the API key from .env and costs one request of that source.
"""

import sys

from app.core.levels import fits_level
from app.core.locations import location_fits
from app.schemas.search import SearchQuery
from app.search_sources.base import SourcePage
from app.search_sources.registry import SOURCE_FACTORIES
from app.search_sources.tavily import TavilySource, is_offer_page, to_offer


def main(args: list[str]) -> None:
    if len(args) < 2:
        print(__doc__)
        return
    name, position, cities = args[0], args[1], args[2:]
    source = SOURCE_FACTORIES[name]()
    query = SearchQuery(position=position, locations=cities)
    print(f'Phrase sent: {query.text()!r}')

    if isinstance(source, TavilySource):
        body = source.build_body(query)
        print(f'Body: {body}')
        rows = source.send(body)
        print(f'Tavily sent {len(rows)} rows:')
        for row in rows:
            title, url = str(row.get('title')), row.get('url')
            print(f'  [{"offer" if is_offer_page(url, title) else "LIST "}] {title}  <{url}>')
        offers = [o for row in rows if (o := to_offer(row, query.cities())) is not None]
        page = SourcePage(offers=offers, skipped=len(rows) - len(offers))
    else:
        page = source.search(query, 10)

    wanted = query.wanted_level()
    print(f'\n{len(page.offers)} offers after mapping ({page.skipped} skipped by the source):')
    for offer in page.offers:
        level_ok = not wanted or fits_level(offer.title, offer.experience_level, wanted)
        city_ok = location_fits(offer.location, query.cities())
        verdict = (
            'shown'
            if level_ok and city_ok
            else 'hidden: ' + ('level' if not level_ok else f'city ({offer.location})')
        )
        print(f'  [{verdict}] {offer.title} | {offer.company_name} | {offer.location}')


if __name__ == '__main__':
    main(sys.argv[1:])
