# JobRadar AI

JobRadar AI is a fullstack web application developed as part of an engineering thesis project. The application supports monitoring, filtering and managing job offers, tracking application statuses and analyzing offer content using an AI assistant module.

This repository contains the source code of the application. The thesis document itself is not included in this repository.

## Local setup

From the repository root:

1. `docker compose up -d postgres` — start the database
2. Copy `backend/.env.example` to `backend/.env` and fill it in
3. `cd backend; uv run alembic upgrade head` — create the tables
4. `just seed` — load the demo job offers (safe to run again; it updates instead of duplicating)
5. `just run` — start the API at http://127.0.0.1:8000/docs
