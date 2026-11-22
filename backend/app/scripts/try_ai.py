"""Send one sample posting to the AI provider from .env and print what it read.

Run from backend/:  uv run python -m app.scripts.try_ai
"""

import time

from app.ai.base import AIProviderError
from app.ai.prompts import offer_parse_messages
from app.ai.structured import AIOutputError, generate
from app.dependencies import ai_provider
from app.schemas.ai import ParsedOffer

SAMPLE_POSTING = """
Junior Python Developer - Codesky (Wrocław, hybrid)
B2B contract, 9 000 - 12 000 PLN net.
You will build REST APIs in Python with FastAPI and PostgreSQL, deployed with Docker.
Nice to have: React, AWS. Apply by 15 December 2026.
"""


def main() -> None:
    provider = ai_provider
    print(f'Provider: {provider.name}, model: {provider.model}, address: {provider.base_url}')
    print(f'Answers: {provider.test()}')

    started = time.perf_counter()
    try:
        offer = generate(provider, offer_parse_messages(SAMPLE_POSTING), ParsedOffer)
    except (AIProviderError, AIOutputError) as err:
        print(f'Failed: {err}')
        return
    print(f'Took {time.perf_counter() - started:.1f} s')
    print(offer.model_dump_json(indent=2))


if __name__ == '__main__':
    main()
