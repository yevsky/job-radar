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


def test_resume_extracted_can_be_empty() -> None:
    assert ResumeExtracted.model_validate({}).skills == []


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
        (ParsedOffer, {'title': 'T', 'experience_level': 'expert'}),
        (ParsedOffer, {'title': 'T', 'technologies': [f't{n}' for n in range(31)]}),
        (OfferAnalysisOutput, {'role_fit': 11, 'summary': 's'}),
        (OfferAnalysisOutput, {'role_fit': 5, 'summary': 's', 'reasons': ['r'] * 6}),
        (ResumeExtracted, {'employment_types': ['freelance']}),
    ],
)
def test_wrong_answers_are_rejected(schema: type[BaseModel], data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(data)
