"""Match analysis: skill matching and the rubric without AI, then analyse() with the fake."""

import json
from typing import Any

import pytest

from app.ai.base import AIProviderError
from app.ai.fake import FakeAIProvider
from app.ai.prompts import OFFER_ANALYSIS_VERSION
from app.ai.structured import AIOutputError
from app.models.enums import EmploymentType, ExperienceLevel
from app.schemas.ai import OfferAnalysisOutput, Requirement
from app.schemas.job_offer import JobOfferImport
from app.schemas.profile import ProfileRead
from app.services.analysis import (
    analyse,
    employment_type_points,
    facts_text,
    level_points,
    location_points,
    match_skills,
    score,
    score_breakdown,
    skill_points,
    with_offer_technologies,
)

J, M, S = ExperienceLevel.JUNIOR, ExperienceLevel.MIDDLE, ExperienceLevel.SENIOR


def req(text: str, skill: str | None = None, required: bool = True) -> Requirement:
    return Requirement(text=text, required=required, skill=skill)


def make_profile(**overrides: Any) -> ProfileRead:
    fields: dict[str, Any] = {
        'experience_level': J,
        'desired_position': 'Python developer',
        'preferred_locations': ['Wrocław', 'Remote'],
        'preferred_employment_types': [EmploymentType.B2B],
        'skills': ['Python', 'FastAPI', 'PostgreSQL'],
    }
    fields.update(overrides)
    return ProfileRead(**fields)


def make_offer(**overrides: Any) -> JobOfferImport:
    fields: dict[str, Any] = {
        'title': 'Junior Python Developer',
        'company_name': 'Codesky',
        'url': 'https://example.com/jobs/1',
        'location': 'Wroclaw',
        'experience_level': J,
        'employment_type': EmploymentType.B2B,
        'technologies': ['Python', 'FastAPI'],
        'description': 'We build APIs with Python and FastAPI. Nice to have: Docker.',
    }
    fields.update(overrides)
    return JobOfferImport(**fields)


def output(**overrides: Any) -> OfferAnalysisOutput:
    fields: dict[str, Any] = {
        'requirements': [
            {'text': 'Python', 'required': True, 'skill': 'Python'},
            {'text': 'FastAPI', 'required': True, 'skill': 'FastAPI'},
        ],
        'role_fit': 10,
        'summary': 'A good fit.',
        'reasons': ['Uses your main stack'],
        'red_flags': [],
    }
    fields.update(overrides)
    return OfferAnalysisOutput.model_validate(fields)


# --- match_skills ---------------------------------------------------------------------


def test_matched_skills_use_the_users_spelling_and_missing_lists_required_gaps() -> None:
    matched, missing = match_skills(
        [
            req('Python 3', 'python'),
            req('REST APIs with FastAPI', ' FASTAPI '),
            req('Kubernetes'),
            req('Docker (nice to have)', required=False),
        ],
        ['Python', 'FastAPI', 'SQL'],
    )
    assert matched == ['Python', 'FastAPI']
    assert missing == ['Kubernetes']  # the nice-to-have isn't "missing"


def test_a_made_up_skill_is_not_matched() -> None:
    """The model said the user's 'Kubernetes' covers it, but the user doesn't have it."""
    matched, missing = match_skills([req('Kubernetes', 'Kubernetes')], ['Python'])
    assert matched == []
    assert missing == ['Kubernetes']


def test_each_skill_is_matched_once() -> None:
    matched, _ = match_skills([req('Python', 'Python'), req('Python 3.12', 'python')], ['Python'])
    assert matched == ['Python']


def test_matched_nice_to_have_counts_as_matched() -> None:
    matched, missing = match_skills([req('Docker', 'Docker', required=False)], ['Docker'])
    assert (matched, missing) == (['Docker'], [])


# --- the rubric, part by part -------------------------------------------------------------


@pytest.mark.parametrize(
    ('requirements', 'expected'),
    [
        ([req('Python', 'Python'), req('SQL', 'SQL')], (45, 10)),  # all required, no nice
        ([req('Python', 'Python'), req('Go')], (22, 10)),  # half: round(22.5) == 22
        ([req('Go'), req('Rust')], (0, 10)),
        ([req('Python', 'Python'), req('a'), req('b')], (15, 10)),  # 1 of 3
        ([req('Docker', 'Docker', required=False), req('K8s', required=False)], (22, 5)),
        ([], (22, 10)),  # the model found nothing: half for required, nothing to miss
    ],
)
def test_skill_points(requirements: list[Requirement], expected: tuple[int, int]) -> None:
    assert skill_points(requirements, ['Python', 'SQL', 'Docker']) == expected


@pytest.mark.parametrize(
    ('offer', 'user', 'expected'),
    [
        (J, J, 20),
        (M, J, 10),
        (ExperienceLevel.TRAINEE, J, 10),
        (S, J, 0),
        (ExperienceLevel.LEAD, J, 0),
        (None, J, 10),
        (J, None, 10),
    ],
)
def test_level_points(
    offer: ExperienceLevel | None, user: ExperienceLevel | None, expected: int
) -> None:
    assert level_points(offer, user) == expected


@pytest.mark.parametrize(
    ('location', 'preferred', 'expected'),
    [
        ('Wroclaw', ['Wrocław'], 10),  # any spelling
        ('Wrocław, Dolnośląskie', ['Wroclaw'], 10),
        ('Remote', ['Warszawa'], 10),  # remote always fits
        ('Praca zdalna', [], 10),
        ('Katowice', ['Wrocław', 'Remote'], 0),
        ('Lisbon', ['Lisbon'], 10),  # a city we don't list
        ('Lisbon', ['Wrocław'], 0),
        (None, ['Wrocław'], 5),
        ('  ', ['Wrocław'], 5),
        ('Katowice', [], 5),  # the user said nothing
    ],
)
def test_location_points(location: str | None, preferred: list[str], expected: int) -> None:
    assert location_points(location, preferred) == expected


@pytest.mark.parametrize(
    ('offer_type', 'preferred', 'expected'),
    [
        (EmploymentType.B2B, [EmploymentType.B2B, EmploymentType.FULL_TIME], 5),
        (EmploymentType.CONTRACT, [EmploymentType.B2B], 0),
        (None, [EmploymentType.B2B], 3),
        (EmploymentType.B2B, [], 3),
    ],
)
def test_employment_type_points(
    offer_type: EmploymentType | None, preferred: list[EmploymentType], expected: int
) -> None:
    assert employment_type_points(offer_type, preferred) == expected


# --- the whole score ------------------------------------------------------------------------


def test_a_perfect_match_scores_100() -> None:
    assert score(make_offer(), make_profile(), output()) == 100


def test_the_breakdown_explains_every_point() -> None:
    breakdown = score_breakdown(
        make_offer(
            location='Katowice',
            experience_level=M,
            employment_type=None,
            technologies=['Python', 'Kubernetes'],  # both already in the requirements
        ),
        make_profile(),
        output(
            requirements=[
                {'text': 'Python', 'required': True, 'skill': 'Python'},
                {'text': 'Kubernetes', 'required': True, 'skill': None},
                {'text': 'Docker', 'required': False, 'skill': None},
            ],
            role_fit=6,
        ),
    )
    assert breakdown.model_dump() == {
        'required_skills': 22,
        'nice_to_have_skills': 0,
        'experience_level': 10,
        'location': 0,
        'employment_type': 3,
        'role_fit': 6,
    }
    assert breakdown.total == 41


def test_the_level_is_guessed_from_the_title_when_the_offer_has_none() -> None:
    offer = make_offer(title='Senior Python Developer', experience_level=None)
    assert score_breakdown(offer, make_profile(), output()).experience_level == 0


def test_a_profile_with_nothing_filled_in_still_gets_a_score() -> None:
    empty = make_profile(
        experience_level=None, preferred_locations=[], preferred_employment_types=[], skills=[]
    )
    breakdown = score_breakdown(make_offer(), empty, output())
    assert breakdown.required_skills == 0  # nothing can be matched
    assert breakdown.total == 0 + 10 + 10 + 5 + 3 + 10


def test_role_fit_over_10_is_rejected() -> None:
    with pytest.raises(ValueError, match='role_fit'):
        output(role_fit=11)


# --- analyse() with the fake ---------------------------------------------------------------

ANSWER = {
    'requirements': [
        {'text': 'Python', 'required': True, 'skill': 'Python'},
        {'text': 'FastAPI', 'required': True, 'skill': 'fastapi'},
        {'text': 'Kubernetes', 'required': True, 'skill': 'Kubernetes'},  # made up
        {'text': 'Docker', 'required': False, 'skill': None},
    ],
    'role_fit': 8,
    'summary': 'Good stack match; Kubernetes is new to you.',
    'reasons': ['Python and FastAPI are your main skills', 'Junior level'],
    'red_flags': ['Unpaid trial task'],
}


def fake(*answers: dict[str, Any] | str) -> FakeAIProvider:
    return FakeAIProvider(responses=[a if isinstance(a, str) else json.dumps(a) for a in answers])


def test_analyse_combines_the_model_answer_and_the_rubric() -> None:
    result = analyse(fake(ANSWER), make_offer(), make_profile())

    assert result.matched_skills == ['Python', 'FastAPI']
    assert result.missing_skills == ['Kubernetes']
    assert result.breakdown.required_skills == 30  # 2 of 3, Kubernetes doesn't count
    assert result.breakdown.nice_to_have_skills == 0
    assert result.score == 30 + 0 + 20 + 10 + 5 + 8
    assert result.summary == ANSWER['summary']
    assert result.reasons == ANSWER['reasons']
    assert result.red_flags == ['Unpaid trial task']
    assert (result.provider, result.model) == ('fake', 'fake')
    assert result.prompt_version == OFFER_ANALYSIS_VERSION


def test_same_answer_gives_the_same_score_every_time() -> None:
    scores = {analyse(fake(ANSWER), make_offer(), make_profile()).score for _ in range(5)}
    assert len(scores) == 1


def test_role_fit_over_10_is_retried() -> None:
    provider = fake(ANSWER, {**ANSWER, 'role_fit': 11}, ANSWER)

    result = analyse(provider, make_offer(), make_profile())

    assert len(provider.calls) == 3  # step 1, step 2, step 2 again
    assert 'role_fit' in provider.calls[2][-1].content
    assert result.breakdown.role_fit == 8


def test_two_bad_answers_raise() -> None:
    with pytest.raises(AIOutputError):
        analyse(fake({**ANSWER, 'role_fit': 50}), make_offer(), make_profile())


def test_provider_errors_go_to_the_caller() -> None:
    with pytest.raises(AIProviderError):
        analyse(FakeAIProvider(fail=True), make_offer(), make_profile())


def test_the_cv_goes_into_the_prompt_when_given() -> None:
    provider = fake(ANSWER)

    analyse(provider, make_offer(), make_profile(), resume_text='Built 3 FastAPI services')

    user_message = provider.calls[1][1].content  # step 2
    assert '<resume>\nBuilt 3 FastAPI services\n</resume>' in user_message


def test_the_prompt_has_the_users_skills_but_not_their_name() -> None:
    provider = fake(ANSWER)

    analyse(provider, make_offer(), make_profile())

    user_message = provider.calls[1][1].content
    assert '"skills": ["Python", "FastAPI", "PostgreSQL"]' in user_message
    assert 'Anna' not in user_message
    assert 'Kowalska' not in user_message


# --- the offer's own technologies and the model's slips ------------------------------------


def test_listed_technologies_the_model_left_out_become_required() -> None:
    requirements = with_offer_technologies(
        [req('Python 3', 'Python'), req('Poszukiwane cechy i umiejętności')],
        ['Django', 'Python', 'SQL'],
    )
    assert [(r.text, r.required) for r in requirements] == [
        ('Python 3', True),
        ('Poszukiwane cechy i umiejętności', True),
        ('Django', True),
        ('SQL', True),
    ]


def test_a_technology_inside_another_word_is_not_counted_as_named() -> None:
    requirements = with_offer_technologies([req('Jython scripting')], ['Python'])
    assert [r.text for r in requirements] == ['Jython scripting', 'Python']


def test_a_requirement_that_is_one_of_the_users_skills_matches_without_skill() -> None:
    """A small model sometimes leaves `skill` empty for 'Django' when the user has Django."""
    matched, missing = match_skills([req('django'), req('Git')], ['Python', 'Django'])
    assert (matched, missing) == (['Django'], ['Git'])


def test_the_analysis_adds_the_offers_technologies() -> None:
    """The real v2 run: the model named only Python and a heading; the offer listed more."""
    answer = output(
        requirements=[
            {'text': 'Python', 'required': True, 'skill': 'Python'},
            {'text': 'Poszukiwane cechy i umiejętności', 'required': True, 'skill': None},
        ]
    )
    provider = FakeAIProvider([json.dumps(answer.model_dump())])
    offer = make_offer(technologies=['Django', 'Git', 'Python', 'SQL'])

    result = analyse(provider, offer, make_profile(skills=['Python', 'SQL']))

    assert result.matched_skills == ['Python', 'SQL']
    assert result.missing_skills == ['Poszukiwane cechy i umiejętności', 'Django', 'Git']


def test_repeated_reasons_and_red_flags_are_shown_once() -> None:
    flag = 'The posting does not say the level.'
    answer = output(reasons=['Python', 'python', ''], red_flags=[flag, flag.upper()])
    assert (answer.reasons, answer.red_flags) == (['Python'], [flag])


# --- offer-analysis-v4: kinds, looser matching, facts for step 2, no contradictions ----------


def kind_req(text: str, kind: str, skill: str | None = None, required: bool = True) -> Requirement:
    return Requirement.model_validate(
        {'text': text, 'required': required, 'kind': kind, 'skill': skill}
    )


def test_traits_and_experience_are_neither_matched_nor_missing() -> None:
    """The real v3 run showed 'Knowledge hungry' as a skill to learn."""
    requirements = [
        kind_req('Python', 'skill', 'Python'),
        kind_req('knowledge hungry', 'trait'),
        kind_req('6-12 months of commercial experience with Python', 'experience'),
        kind_req('English B2', 'language'),
    ]
    assert match_skills(requirements, ['Python']) == (['Python'], [])
    assert skill_points(requirements, ['Python']) == (45, 10)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [('Trait', 'trait'), ('soft skill', 'trait'), (None, 'skill'), ('tool', 'skill')],
)
def test_an_unknown_kind_is_read_leniently(value: str | None, expected: str) -> None:
    assert kind_req('x', value).kind == expected  # type: ignore[arg-type]


def test_a_skill_named_inside_a_requirement_covers_it() -> None:
    """'basic experience with Django' is covered by Django, without the model's help."""
    matched, missing = match_skills(
        [req('basic experience with Django'), req('C#'), req('C++')], ['Django', 'C']
    )
    assert (matched, missing) == (['Django'], ['C#', 'C++'])


def test_a_skill_named_in_the_chosen_cv_counts_as_covered() -> None:
    cv = 'I apply SOLID principles and write unit tests.'
    matched, missing = match_skills([req('SOLID'), req('DRY')], ['Python'], resume_text=cv)
    assert (matched, missing) == (['SOLID'], ['DRY'])


def test_the_facts_for_step_2_say_what_is_covered_and_what_is_not() -> None:
    requirements = [
        kind_req('Python', 'skill', 'Python'),
        kind_req('basic experience with Django', 'skill'),
        kind_req('Docker', 'skill', required=False),
        kind_req('knowledge hungry', 'trait'),
        kind_req('6-12 months of commercial experience', 'experience'),
    ]
    facts = facts_text(make_offer(), make_profile(), requirements)
    assert 'Skills the candidate covers: Python' in facts
    assert 'Required skills the candidate lacks: basic experience with Django' in facts
    assert 'Nice-to-have skills the candidate lacks: Docker' in facts
    assert 'Other demands of the posting: 6-12 months of commercial experience (experience)' in (
        facts
    )
    assert 'knowledge hungry' not in facts
    assert 'Offer level: junior; candidate level: junior' in facts
    assert "Location: Wroclaw (fits the candidate's preferences)" in facts


def test_step_2_gets_the_facts_from_step_1() -> None:
    provider = fake(ANSWER)
    analyse(provider, make_offer(), make_profile())
    assert '<facts>\nSkills the candidate covers: Python, FastAPI' in provider.calls[1][1].content


def test_red_flags_about_a_covered_skill_or_repeating_a_reason_are_dropped() -> None:
    """The real v3 run: 'SQL ... which you have' as a reason and as a red flag."""
    step_1 = {'requirements': [{'text': 'SQL', 'required': True, 'skill': 'SQL'}]}
    step_2 = {
        'role_fit': 9,
        'summary': 'A good fit.',
        'reasons': ['Small team, mentoring offered'],
        'red_flags': [
            'Hands-on experience with SQL might be a bit high for a junior',
            'small team, mentoring offered',
            'No salary given',
        ],
    }
    provider = fake(step_1, step_2)

    result = analyse(provider, make_offer(technologies=[]), make_profile(skills=['SQL']))

    assert result.red_flags == ['No salary given']
