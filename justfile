set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set working-directory := "backend"

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

run-backend:
    uv run fastapi dev app/main.py

run-frontend:
    npm --prefix ../frontend run dev

[parallel]
run: run-backend run-frontend

seed:
    uv run python -m app.scripts.seed

frontend-check:
    npm --prefix ../frontend run check

frontend-test:
    npm --prefix ../frontend test