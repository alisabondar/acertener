# Development

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL 16 · Alembic (backend, `uv`)
· Vite+ · React · TypeScript · TanStack Query · shadcn/ui (frontend, Bun)

## Developing without Docker for the app

**Needs:** Docker (for Postgres), uv, Bun ≥ 1.4.3, pre-commit, and gitleaks.

```bash
cp .env.example .env
docker compose up -d --wait db          # Postgres on 127.0.0.1:5432
pre-commit install                      # secret scan + lint on every commit

cd backend && uv sync && uv run alembic upgrade head
uv run python -m scripts.seed           # 10,000 patients; --count N, --reset
uv run uvicorn --factory app.main:create_app --reload

cd frontend && bun install && bun run dev   # http://localhost:5173, /api proxied to :8000
```

| What | Command |
|---|---|
| All lint, format, and type checks | `pre-commit run --all-files` |
| Backend tests (needs the `db` container) / without Docker | `uv run pytest` / `uv run pytest -m "not db"` |
| Privacy canaries | `uv run pytest -m privacy` |
| Frontend lint, format, types, tests / coverage gate | `bun run check` / `bun run test:coverage` |
| End-to-end (API and Vite running) | `bun run test:e2e` |
| Regenerate API types after a schema change | `bun run api:types` |
| New migration | `uv run alembic revision -m "describe change"` |
| Query plans / single-client latency | `uv run python -m scripts.explain_queries` / `scripts.time_endpoints` |
| Load test (50 staff, 3 minutes) | `uv run locust -f loadtest/locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 -t 3m` |
| Add ~1M simulated audit rows | `uv run python -m scripts.simulate_audit` |
| Encryption proof (needs `pg_dump` on the host) | `uv run python -m scripts.prove_encryption` |

Run backend commands from `backend/` and frontend commands from `frontend/`.

## Configuration

All config comes from environment variables; see [`.env.example`](../.env.example). `./dev.sh`
creates `.env` on first run. **Never commit `.env`.**

| Variable | Purpose |
|---|---|
| `ENV` | `development` (default), `test`, or `production`. Seeding runs only in `development`. |
| `DEMO_MODE` | Turns on the persona picker. Refused when `ENV=production` or `ENV` is unset. |
| `SUMMARY_PROVIDER` | `auto` (Gemini when a key is set, otherwise the mock), `mock`, `gemini`, or `baa` (the production slot for a BAA-covered provider; refuses to start until implemented). |
| `GEMINI_API_KEY` | Optional free key from Google AI Studio. Synthetic data only; see [production readiness](security.md#production-readiness). |
| `CORS_ORIGINS` | Browser origins allowed to call the API (comma-separated; `*` is refused). |
| `PRACTICE_TIMEZONE` | The practice's IANA timezone; defines "today". Default `America/New_York`. |
| `INACTIVE_AFTER_YEARS` | Years without a visit before a patient is flagged as possibly inactive. Default `3`. |
| `KEYS_DIR` | Where encryption keys live (the `keys` volume in Docker, `.keys/` on the host). Losing them makes encrypted data unreadable. |
| `POSTGRES_*`, `DATABASE_URL`, `TEST_DATABASE_URL` | Local database settings (dev-only credentials). |
