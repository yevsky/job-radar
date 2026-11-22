import pytest

from app.core.levels import (
    cap_level_by_years,
    fits_level,
    guess_level,
    is_close,
    level_for_years,
    level_from_years,
    levels_in,
    remove_levels,
)
from app.models.enums import ExperienceLevel

TRAINEE = ExperienceLevel.TRAINEE
JUNIOR = ExperienceLevel.JUNIOR
MIDDLE = ExperienceLevel.MIDDLE
SENIOR = ExperienceLevel.SENIOR
LEAD = ExperienceLevel.LEAD


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Junior Python Developer', [JUNIOR]),
        ('Python Developer (Junior/Mid)', [JUNIOR, MIDDLE]),
        ('Starszy Programista Python (k/m)', [SENIOR]),
        ('Młodszy specjalista ds. testów', [JUNIOR]),
        ('AI Engineer Intern Krakow', [TRAINEE]),
        ('Stażysta w dziale IT', [TRAINEE]),
        ('Associate Technical Consultant (Entry-Level)', [JUNIOR]),
        ('Regular Java Developer', [MIDDLE]),
        ('Tech Lead / Principal Engineer', [LEAD]),
        ('Sr. Backend Engineer', [SENIOR]),
        ('Python Developer', []),
        ('Juniorska rola', []),  # whole words only
        ('Team leader in sales', []),  # 'leader' is not 'lead'
    ],
)
def test_levels_in(text: str, expected: list[ExperienceLevel]) -> None:
    assert levels_in(text) == expected


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Senior Python developer', 'Python developer'),
        ('Junior / Mid Python developer', 'Python developer'),
        ('python developer', 'python developer'),
        ('Senior', ''),
    ],
)
def test_remove_levels(text: str, expected: str) -> None:
    assert remove_levels(text) == expected


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('no experience needed, 0 years', TRAINEE),
        ('at least 1 year with Python', JUNIOR),
        ('2+ years of commercial experience', MIDDLE),  # junior is under 2
        ('3 years of experience', MIDDLE),
        ('minimum 4 lata doświadczenia', MIDDLE),
        ('6+ years in software engineering', SENIOR),
        ('10 lat doświadczenia', SENIOR),
        ('Python, Django, Docker', None),
    ],
)
def test_level_from_years(text: str, expected: ExperienceLevel | None) -> None:
    assert level_from_years(text) == expected


def test_title_wins_over_years() -> None:
    assert guess_level('Junior Developer', '5+ years of experience') == JUNIOR
    assert guess_level('Developer', '5+ years of experience') == SENIOR
    assert guess_level('Developer', None) is None


@pytest.mark.parametrize(
    ('level', 'wanted', 'expected'),
    [
        (TRAINEE, JUNIOR, True),
        (JUNIOR, JUNIOR, True),
        (MIDDLE, JUNIOR, True),
        (SENIOR, JUNIOR, False),
        (LEAD, JUNIOR, False),
        (MIDDLE, SENIOR, True),
        (LEAD, SENIOR, True),
        (JUNIOR, SENIOR, False),
    ],
)
def test_is_close(level: ExperienceLevel, wanted: ExperienceLevel, expected: bool) -> None:
    assert is_close(level, wanted) is expected


def test_fits_level() -> None:
    assert fits_level('Junior Python Developer', None, JUNIOR)
    assert not fits_level('Senior Python Developer', None, JUNIOR)
    assert fits_level('Python Developer (Mid/Senior)', None, JUNIOR)  # mid is close enough
    assert not fits_level('Python Developer', SENIOR, JUNIOR)  # level from the source
    assert fits_level('Python Developer', None, JUNIOR)  # unknown level: kept


T, J, M, S, L = (
    ExperienceLevel.TRAINEE,
    ExperienceLevel.JUNIOR,
    ExperienceLevel.MIDDLE,
    ExperienceLevel.SENIOR,
    ExperienceLevel.LEAD,
)


@pytest.mark.parametrize(
    ('years', 'expected'),
    [(0, T), (0.75, T), (1, J), (1.9, J), (2, M), (4.5, M), (5, S), (10, S)],
)
def test_level_for_years(years: float, expected: ExperienceLevel) -> None:
    assert level_for_years(years) == expected


@pytest.mark.parametrize(
    ('level', 'years', 'expected'),
    [
        (S, 0.75, J),  # a student read as senior: under a year is at most junior
        (S, 3, M),
        (S, 6, S),
        (L, 10, S),  # years alone never make a lead: capped at senior
        (T, 0.5, T),  # an intern stays an intern
        (J, 6, J),  # never raised: the cap only lowers
        (None, 0.75, J),  # no level from the model: the years decide
        (None, 3, M),
        (S, None, S),  # no years: the model's level stays
        (None, None, None),
    ],
)
def test_cap_level_by_years(
    level: ExperienceLevel | None, years: float | None, expected: ExperienceLevel | None
) -> None:
    assert cap_level_by_years(level, years) == expected
