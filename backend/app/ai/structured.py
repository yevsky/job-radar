"""Turn a model's text answer into a Pydantic model, asking once more when it doesn't fit."""

from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider, ChatMessage
from app.core.validation import format_errors

RETRY_PROMPT = (
    'Your answer did not match the schema: {errors}. '
    'Answer again with only the corrected JSON object, no other text.'
)


class AIOutputError(Exception):
    """The model answered twice, and neither answer matched the schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors  # one short error text per answer
        super().__init__('The AI answer did not match the schema: ' + ' | '.join(errors))


class AnswerError(Exception):
    """One answer can't be used: no JSON in it, broken JSON, or wrong fields."""


def extract_json(text: str) -> str | None:
    """Return the part from the first '{' to the last '}', or None if there's no object.

    This drops ```json fences and sentences the model wrote before or after the JSON.
    """
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end < start:
        return None
    return text[start : end + 1]


def parse_answer[T: BaseModel](text: str, schema: type[T]) -> T:
    """Read one answer as schema; raise AnswerError with a short reason if it doesn't fit."""
    json_text = extract_json(text)
    if json_text is None:
        raise AnswerError('the answer contains no JSON object')
    try:
        return schema.model_validate_json(json_text)
    except ValidationError as err:
        raise AnswerError(format_errors(err, root='answer')) from err


def generate[T: BaseModel](provider: AIProvider, messages: list[ChatMessage], schema: type[T]) -> T:
    """Ask the model and return its answer as `schema`.

    If the first answer doesn't fit, the model gets its own answer back with the errors
    and one more try. A second bad answer raises AIOutputError. AIProviderError (the call
    itself failed) is not retried here: it goes straight to the caller.
    """
    answer = provider.chat(messages, json_mode=True)
    try:
        return parse_answer(answer, schema)
    except AnswerError as err:
        first_error = str(err)

    retry = [
        *messages,
        ChatMessage(role='assistant', content=answer),
        ChatMessage(role='user', content=RETRY_PROMPT.format(errors=first_error)),
    ]
    second_answer = provider.chat(retry, json_mode=True)
    try:
        return parse_answer(second_answer, schema)
    except AnswerError as err:
        raise AIOutputError([first_error, str(err)]) from err
