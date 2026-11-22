from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.ai import OfferAnalysisOutput, ParsedOffer, ResumeExtracted


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
