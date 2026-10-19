# The API image, also used for the one-shot keys-init, migrate, and seed services.
# Development image: dev dependencies are included so `./dev.sh test` can run inside it.
FROM python:3.12-slim-trixie

# pg_dump for the encryption proof (Postgres 17's client dumps a 16 server).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

# The environment lives outside the source folder, so mounting the source doesn't hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY . .

RUN useradd --create-home --uid 1000 app && mkdir -p /keys && chown app /keys /opt/venv
USER app

EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
