from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.ai import (
    OfferAnalysisOutput,
    ParsedOffer,
    ResumeExtracted,
    WorkPeriod,
    month_of,
    years_of_work,
)


def test_parsed_offer_needs_only_a_title() -> None:
    offer = ParsedOffer.model_validate({'title': ' Tester '})
    assert offer.title == 'Tester'
    assert offer.company_name is None
    assert offer.technologies == []


def test_extra_fields_from_the_model_are_ignored() -> None:
    offer = ParsedOffer.model_validate({'title': 'Tester', 'salary': '10k', 'mood': 'happy'})
    assert offer.model_dump().keys() == ParsedOffer.model_fields.keys()


@pytest.mark.parametrize(
    ('word', 'expected'),
    [
        ('junior', 'junior'),
        (' Senior ', 'senior'),
        ('expert', None),  # not one of our levels: dropped, not an error
        (None, None),
    ],
)
def test_unknown_level_becomes_none(word: str | None, expected: str | None) -> None:
    offer = ParsedOffer.model_validate({'title': 'T', 'experience_level': word})
    assert offer.experience_level == expected


@pytest.mark.parametrize(
    ('word', 'expected'),
    [('B2B', 'b2b'), ('Full-time', 'full_time'), ('full time', 'full_time'), ('freelance', None)],
)
def test_employment_type_is_read_loosely(word: str, expected: str | None) -> None:
    offer = ParsedOffer.model_validate({'title': 'T', 'employment_type': word})
    assert offer.employment_type == expected


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('2026-12-15', date(2026, 12, 15)),
        ('2026-12-15T23:59:00', date(2026, 12, 15)),
        ('ASAP', None),
        ('15 December', None),
        (20261215, None),
    ],
)
def test_deadline_that_isnt_a_date_becomes_none(value: object, expected: date | None) -> None:
    assert ParsedOffer.model_validate({'title': 'T', 'deadline': value}).deadline == expected


def test_odd_technologies_are_dropped_and_repeats_removed() -> None:
    names = ['Python', ' python ', '', 42, 'x' * 51, 'FastAPI']
    offer = ParsedOffer.model_validate({'title': 'T', 'technologies': names})
    assert offer.technologies == ['Python', 'FastAPI']


def test_resume_extracted_can_be_empty() -> None:
    assert ResumeExtracted.model_validate({}).skills == []


def test_resume_extracted_cleans_lists_instead_of_failing() -> None:
    extracted = ResumeExtracted.model_validate(
        {
            'skills': ['Python', ' python ', '', 7, 'x' * 51, *[f's{n}' for n in range(60)]],
            'locations': ['Wrocław', 'wrocław', 'Remote'],
            'employment_types': ['B2B', 'freelance', 'b2b', 'Full-time'],
            'experience_level': 'expert',
        }
    )
    assert extracted.skills[:2] == ['Python', 's0']
    assert len(extracted.skills) == 50
    assert extracted.locations == ['Wrocław', 'Remote']
    assert extracted.employment_types == ['b2b', 'full_time']
    assert extracted.experience_level is None


def test_resume_extracted_level_is_capped_by_the_years() -> None:
    """The real v1 run: a student with under a year of work, read as senior."""
    extracted = ResumeExtracted.model_validate(
        {'experience_level': 'Senior', 'experience_years': 0.75}
    )
    assert extracted.experience_level == 'junior'
    assert extracted.experience_years == 0.75


def test_resume_extracted_counts_the_years_from_the_jobs() -> None:
    """The real v2 run: the same student came out as middle. The model's own years and
    level lose to the dates it copied."""
    today = date.today()
    months = today.year * 12 + today.month - 1 - 4  # four months ago, counted from 0
    four_months_ago = date(months // 12, months % 12 + 1, 1)
    extracted = ResumeExtracted.model_validate(
        {
            'experience_level': 'middle',
            'experience_years': 3,
            'jobs': [
                {'title': 'Python intern', 'start': four_months_ago.isoformat(), 'end': 'present'},
                {'title': 'Tutor', 'start': '2019', 'end': '2018'},  # ends before it starts
                {'title': 'Something', 'start': 'once'},  # no readable start
            ],
        }
    )
    assert [job.title for job in extracted.jobs or []] == ['Python intern']
    assert extracted.experience_years == round(5 / 12, 2)  # four months ago up to this one
    assert extracted.experience_level == 'junior'


def test_no_jobs_means_no_years_of_work() -> None:
    extracted = ResumeExtracted.model_validate({'experience_level': 'senior', 'jobs': []})
    assert (extracted.experience_years, extracted.experience_level) == (0, 'junior')


def test_without_jobs_the_models_years_stay() -> None:
    extracted = ResumeExtracted.model_validate({'experience_years': 3, 'jobs': 'none'})
    assert (extracted.jobs, extracted.experience_years) == (None, 3)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('2026-03', date(2026, 3, 1)),
        ('2026-03-15', date(2026, 3, 1)),
        ('03/2026', date(2026, 3, 1)),
        ('3.2026', date(2026, 3, 1)),
        ('2026', date(2026, 1, 1)),
        (date(2026, 3, 15), date(2026, 3, 1)),
        ('present', None),
        ('obecnie', None),
        ('2026-13', None),
        ('march', None),
        (None, None),
        (2026, None),
    ],
)
def test_month_of(value: object, expected: date | None) -> None:
    assert month_of(value) == expected


def job(start: str, end: str | None) -> WorkPeriod:
    return WorkPeriod.model_validate({'start': start, 'end': end})


def test_years_of_work_counts_overlapping_months_once() -> None:
    today = date(2026, 11, 1)
    jobs = [job('2025-01', '2025-12'), job('2025-07', '2026-06'), job('2026-10', None)]
    # 2025-01..2026-06 is 18 months, plus October and November 2026
    assert years_of_work(jobs, today) == round(20 / 12, 2)


def test_years_of_work_stops_at_today() -> None:
    assert years_of_work([job('2026-09', '2030-01')], date(2026, 11, 1)) == round(3 / 12, 2)
    assert years_of_work([], date(2026, 11, 1)) == 0


@pytest.mark.parametrize('years', ['a few', -1, 99, True, None, [1]])
def test_resume_extracted_drops_impossible_years(years: object) -> None:
    extracted = ResumeExtracted.model_validate(
        {'experience_level': 'senior', 'experience_years': years}
    )
    assert extracted.experience_years is None
    assert extracted.experience_level == 'senior'  # without years the model's level stays


def test_resume_extracted_cuts_long_texts() -> None:
    extracted = ResumeExtracted.model_validate(
        {'desired_position': ' ' + 'p' * 200, 'summary': 's' * 900}
    )
    assert extracted.desired_position == 'p' * 120
    assert extracted.summary is not None
    assert len(extracted.summary) == 500
    assert ResumeExtracted.model_validate({'summary': '   '}).summary is None


def test_analysis_output_reads_requirements() -> None:
    output = OfferAnalysisOutput.model_validate(
        {
            'requirements': [
                {'text': 'Python', 'required': True, 'skill': 'Python'},
                {'text': 'Docker', 'required': False, 'skill': None},
            ],
            'role_fit': 8,
            'summary': 'Good fit.',
        }
    )
    assert output.requirements[0].skill == 'Python'
    assert output.requirements[1].required is False
    assert output.red_flags == []


@pytest.mark.parametrize(
    ('schema', 'data'),
    [
        (ParsedOffer, {}),
        (ParsedOffer, {'title': 'T', 'technologies': [f't{n}' for n in range(31)]}),
        (OfferAnalysisOutput, {'role_fit': 11, 'summary': 's'}),
        (OfferAnalysisOutput, {'role_fit': 5, 'summary': 's', 'reasons': ['r'] * 6}),
        (ResumeExtracted, {'skills': 'Python'}),  # not a list at all
    ],
)
def test_wrong_answers_are_rejected(schema: type[BaseModel], data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(data)
