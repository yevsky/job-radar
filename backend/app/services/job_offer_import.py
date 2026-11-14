from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    'ref',
    'refid',
    'trk',
    'trackingid',
    'gh_src',
    'lever-source',
    'fbclid',
    'gclid',
    'msclkid',
    'src',
}


def is_tracking_param(name: str) -> bool:
    name = name.lower()
    return name.startswith('utm_') or name in TRACKING_PARAMS


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix('www.')
    path = parts.path.rstrip('/')
    query = sorted(
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not is_tracking_param(name)
    )
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ''))
