# Patient Dashboard

A clinician-facing patient dashboard, built HIPAA-ready from day one. All data is synthetic.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL 16 · Alembic (backend, `uv`)
· Vite+ · React · TypeScript · TanStack Query · shadcn/ui (frontend, Bun)

## Quick start

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh) ≥ 1.4.3,
`gitleaks`, and `pre-commit`. Vite+ comes with the frontend's dependencies.

```bash
cp .env.example .env                 # once
docker compose up -d --wait db       # Postgres on 127.0.0.1:5432
pre-commit install                   # once: secret scan + lint on every commit

cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed       # 10,000 synthetic patients and the demo personas (~1 min)
uv run uvicorn --factory app.main:create_app --reload
```

In a second terminal:

```bash
cd frontend
bun install
bun run dev                          # http://localhost:5173; /api is proxied to the API on :8000
```

- App: http://localhost:5173. There's no login: it starts as **Dr. Chen**, and **Switch** in the
  banner (or the avatar menu) changes who you're acting as. Navigation and pages follow the
  persona's role; the API enforces every permission regardless.
- API: http://localhost:8000 · Interactive docs: http://localhost:8000/docs
- Calling the API directly: `GET /api/v1/personas` lists the demo personas; send `X-Persona: <id>` to act as one
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
| Frontend tests only | `cd frontend && bun run test` |
| Regenerate API types after a backend schema change (CI fails if they're stale) | `cd frontend && bun run api:types` |
| New migration | `cd backend && uv run alembic revision -m "describe change"` |
| Seed the dev database (10,000 by default; `--count N`, `--reset` to start over) | `cd backend && uv run python -m scripts.seed` |
| Performance checks (see [`docs/performance.md`](docs/performance.md)) | `cd backend && uv run python -m scripts.explain_queries` · `scripts.time_endpoints` (API running) |
| Prove encryption (app view vs raw rows vs `pg_dump`) | `cd backend && uv run python -m scripts.prove_encryption` |

## Configuration

All config comes from environment variables. See [`.env.example`](.env.example). Never commit `.env`.

| Variable | Purpose |
|---|---|
| `ENV` | `development` (default), `test`, or `production`. Seeding runs only in `development`. |
| `DEMO_MODE` | Turns on the persona picker; there's no login in the MVP. Refused when `ENV=production` or `ENV` is unset. |
| `CORS_ORIGINS` | Browser origins allowed to call the API (comma-separated; `*` is refused). Default `http://localhost:5173`. |
| `PRACTICE_TIMEZONE` | The practice's IANA timezone; defines "today" (today's visits, ages). Default `America/New_York`. |
| `INACTIVE_AFTER_YEARS` | Years without a visit before a patient is flagged as possibly inactive. Default `3`. |
| `KEYS_DIR` | Where encryption keys live (default `.keys/`). **Deleting them makes encrypted data unreadable**, so reset keys and the database together. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Local Docker Postgres credentials (dev only) |
| `POSTGRES_PORT` | Host port for Postgres. If you change it, update both URLs below. |
| `DATABASE_URL` | API database (`postgresql+asyncpg://…`) |
| `TEST_DATABASE_URL` | Test database (`app_test`, created automatically) |
