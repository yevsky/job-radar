import pytest
from pydantic import BaseModel, ValidationError

from app.core.validation import format_errors


class Offer(BaseModel):
    title: str
    salary: int


def errors_of(data: object) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        Offer.model_validate(data)
    return caught.value


def test_one_line_with_every_field() -> None:
    error = errors_of({'salary': 'a lot'})
    assert format_errors(error) == (
        'title: Field required; '
        'salary: Input should be a valid integer, unable to parse string as an integer'
    )


def test_error_about_the_whole_value_uses_root_name() -> None:
    error = errors_of('not an object')
    assert format_errors(error).startswith('row: ')
    assert format_errors(error, root='answer').startswith('answer: ')
