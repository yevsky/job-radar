set shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

check:
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy .
    uv run pytest

format:
    uv run ruff format .
    uv run ruff check . --fix

lint:
    uv run ruff check .

typecheck:
    uv run mypy .

test:
    uv run pytest

run:
    uv run fastapi dev app/main.py