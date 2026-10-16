# Patient Dashboard

A clinician-facing patient dashboard, built HIPAA-ready from day one. All data is synthetic.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL 16 · Alembic (backend, `uv`)
· Vite+ · React · TypeScript (frontend, Bun)

## Quick start

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh) ≥ 1.4.3,
Vite+ (`bun add -g vite-plus`), `gitleaks`, and `pre-commit`.

```bash
cp .env.example .env                 # once
docker compose up -d --wait db       # Postgres on 127.0.0.1:5432
pre-commit install                   # once: secret scan + lint on every commit

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn --factory app.main:create_app --reload
```

- API: http://localhost:8000 · Interactive docs: http://localhost:8000/docs
- Health: `GET /health` (process is up) and `GET /health/ready` (database reachable, otherwise `503`)

## Commands

| What | Command |
|---|---|
| All lint, format, and type checks | `pre-commit run --all-files` |
| Backend tests (needs the `db` container) | `cd backend && uv run pytest` |
| Backend tests without Docker | `cd backend && uv run pytest -m "not db"` |
| Backend tests with the coverage gate (80%) | `cd backend && uv run pytest --cov` |
| Frontend lint, format, types, tests | `cd frontend && bun run check` |
| New migration | `cd backend && uv run alembic revision -m "describe change"` |

## Configuration

All config comes from environment variables. See [`.env.example`](.env.example). Never commit `.env`.

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Local Docker Postgres credentials (dev only) |
| `POSTGRES_PORT` | Host port for Postgres. If you change it, update both URLs below. |
| `DATABASE_URL` | API database (`postgresql+asyncpg://…`) |
| `TEST_DATABASE_URL` | Test database (`app_test`, created automatically) |
| `VITE_API_BASE_URL` | Frontend API prefix (browser-visible, so never put secrets in it) |
