"""Experience levels in free text: job titles, the search form and offer descriptions."""

import re

from app.models.enums import ExperienceLevel

# From least to most experienced; "close" means at most one step apart.
LADDER = [
    ExperienceLevel.TRAINEE,
    ExperienceLevel.JUNIOR,
    ExperienceLevel.MIDDLE,
    ExperienceLevel.SENIOR,
    ExperienceLevel.LEAD,
]

# Words job boards use for each level, in English and Polish.
LEVEL_WORDS = {
    ExperienceLevel.TRAINEE: [
        'intern',
        'internship',
        'trainee',
        'stażysta',
        'stażystka',
        'staż',
        'praktykant',
        'praktykantka',
    ],
    ExperienceLevel.JUNIOR: [
        'junior',
        'jr',
        'młodszy',
        'młodsza',
        'entry-level',
        'entry level',
        'graduate',
        'absolwent',
    ],
    ExperienceLevel.MIDDLE: ['mid', 'middle', 'mid-level', 'regular'],
    ExperienceLevel.SENIOR: ['senior', 'sr', 'starszy', 'starsza', 'expert', 'ekspert'],
    ExperienceLevel.LEAD: ['lead', 'principal', 'head of', 'architect', 'kierownik'],
}

# A whole word only: 'Junior' matches, 'Juniorska' and 'leader' don't.
LEVEL_PATTERNS = {
    level: re.compile(
        r'(?<!\w)(?:' + '|'.join(re.escape(word) for word in words) + r')(?!\w)', re.IGNORECASE
    )
    for level, words in LEVEL_WORDS.items()
}

# '3+ years', '5 years', '2 lata', '6 lat'
YEARS = re.compile(r'(?<!\d)(\d{1,2})\s*\+?\s*(?:years?|yrs|lata|lat)(?!\w)', re.IGNORECASE)


def levels_in(text: str) -> list[ExperienceLevel]:
    """Every level named in the text, least first: 'Junior/Mid Dev' -> [JUNIOR, MIDDLE]."""
    return [level for level in LADDER if LEVEL_PATTERNS[level].search(text)]


def remove_levels(text: str) -> str:
    """The text without level words: 'Senior Python developer' -> 'Python developer'."""
    for pattern in LEVEL_PATTERNS.values():
        text = pattern.sub(' ', text)
    return ' '.join(text.replace(' / ', ' ').split())


def level_from_years(text: str) -> ExperienceLevel | None:
    """The level the first 'N years' in the text asks for; None if there is no such phrase."""
    match = YEARS.search(text)
    if match is None:
        return None
    years = int(match.group(1))
    if years < 1:
        return ExperienceLevel.TRAINEE
    if years <= 2:
        return ExperienceLevel.JUNIOR
    if years <= 4:
        return ExperienceLevel.MIDDLE
    return ExperienceLevel.SENIOR


def guess_level(title: str, description: str | None = None) -> ExperienceLevel | None:
    """The offer's level: from the title, else from 'N years' in the description."""
    in_title = levels_in(title)
    if in_title:
        return in_title[0]
    return level_from_years(description or '')


def is_close(level: ExperienceLevel, wanted: ExperienceLevel) -> bool:
    """True if the levels are at most one step apart: a junior also sees trainee and middle."""
    return abs(LADDER.index(level) - LADDER.index(wanted)) <= 1


def fits_level(title: str, level: ExperienceLevel | None, wanted: ExperienceLevel) -> bool:
    """Should an offer be shown to someone looking for `wanted`?

    'Junior/Mid' fits if any of its levels is close. An offer whose level we can't tell
    is kept: better one extra result than hiding a good one.
    """
    levels = levels_in(title) or ([level] if level else [])
    return not levels or any(is_close(found, wanted) for found in levels)
