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
uv run python -m scripts.seed       # 20 synthetic patients, personas, and a developer account
uv run uvicorn --factory app.main:create_app --reload
```

- API: http://localhost:8000 · Interactive docs: http://localhost:8000/docs
- No login: `GET /api/v1/personas` lists the demo personas; send `X-Persona: <id>` to act as one
  (in `/docs`, add the header per request). Every action is permission-checked and audited.
- Health: `GET /health` (process is up) and `GET /health/ready` (database reachable, otherwise `503`)
- Encryption keys are created in `.keys/` on first start. Patient identifiers and clinical free text
  are encrypted in the database; only the app can read them.

## Commands

| What | Command |
|---|---|
| All lint, format, and type checks | `pre-commit run --all-files` |
| Backend tests (needs the `db` container) | `cd backend && uv run pytest` |
| Backend tests without Docker | `cd backend && uv run pytest -m "not db"` |
| Backend tests with the coverage gate (80%) | `cd backend && uv run pytest --cov` |
| Frontend lint, format, types, tests | `cd frontend && bun run check` |
| New migration | `cd backend && uv run alembic revision -m "describe change"` |
| Seed the dev database (`--count N`, `--reset` to start over) | `cd backend && uv run python -m scripts.seed` |
| Prove encryption (app view vs raw rows vs `pg_dump`) | `cd backend && uv run python -m scripts.prove_encryption` |

## Configuration

All config comes from environment variables. See [`.env.example`](.env.example). Never commit `.env`.

| Variable | Purpose |
|---|---|
| `ENV` | `development` (default), `test`, or `production`. Seeding runs only in `development`. |
| `DEMO_MODE` | Turns on the persona picker; there's no login in the MVP. Refused when `ENV=production` or `ENV` is unset. |
| `KEYS_DIR` | Where encryption keys live (default `.keys/`). **Deleting them makes encrypted data unreadable**, so reset keys and the database together. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Local Docker Postgres credentials (dev only) |
| `POSTGRES_PORT` | Host port for Postgres. If you change it, update both URLs below. |
| `DATABASE_URL` | API database (`postgresql+asyncpg://…`) |
| `TEST_DATABASE_URL` | Test database (`app_test`, created automatically) |
| `VITE_API_BASE_URL` | Frontend API prefix (browser-visible, so never put secrets in it) |
