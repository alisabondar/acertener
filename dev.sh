#!/usr/bin/env bash
# One command for the whole app. Docker is the only prerequisite (macOS/Linux; Windows via WSL).
#
#   ./dev.sh                     start everything (first run builds images and seeds 10k patients)
#   ./dev.sh reset [--count N]   wipe the database and encryption keys together, then reseed
#   ./dev.sh test [backend|frontend|e2e|privacy]   run tests in containers (default: all)
#   ./dev.sh proof               show that patient data is encrypted at rest
#   ./dev.sh stop                stop the containers (data is kept)
set -euo pipefail
cd "$(dirname "$0")"

compose() { docker compose "$@"; }

require_docker() {
  if ! docker info > /dev/null 2>&1; then
    echo "Docker isn't running. Start Docker Desktop (or the Docker daemon) and try again." >&2
    exit 1
  fi
}

# Fails fast, before a long build, if something outside this stack holds a port it needs.
require_free_ports() {
  local port owner
  for port in 5173 8000 "$(grep -E '^POSTGRES_PORT=' .env 2> /dev/null | cut -d= -f2 || true)"; do
    port="${port:-5432}"
    if compose ps --format '{{.Ports}}' 2> /dev/null | grep -q "127.0.0.1:$port->"; then
      continue # already ours
    fi
    if (exec 3<> "/dev/tcp/127.0.0.1/$port") 2> /dev/null; then
      owner="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2> /dev/null | awk 'NR == 2 { print $1 " (pid " $2 ")" }' || true)"
      echo "Port $port is already in use${owner:+ by $owner}. Stop it and run ./dev.sh again." >&2
      exit 1
    fi
  done
}

ensure_env() {
  [[ -f .env ]] && return
  cp .env.example .env
  echo "Created .env from .env.example."
  if [[ -t 0 ]]; then
    read -r -s -p "Paste a Gemini API key for real AI summaries, or press Enter to use the built-in mock: " key
    echo
    if [[ -n "$key" ]]; then
      # Written only to .env, which git ignores. A temp file keeps this portable across sed flavours.
      grep -v '^GEMINI_API_KEY=' .env > .env.tmp && echo "GEMINI_API_KEY=$key" >> .env.tmp
      mv .env.tmp .env
      echo "Saved to .env (never commit it)."
    fi
  fi
}

wait_until_up() {
  echo "Waiting for the app (the first run seeds 10,000 patients, about a minute)..."
  for _ in $(seq 1 180); do
    if curl -fs http://localhost:5173 > /dev/null 2>&1 && curl -fs http://localhost:8000/health/ready > /dev/null 2>&1; then
      return 0
    fi
    if compose ps -a --format '{{.Service}} {{.State}} {{.ExitCode}}' | grep -qE '^(keys-init|migrate|seed) exited [1-9]'; then
      echo "A setup step failed. Its logs:" >&2
      compose logs keys-init migrate seed >&2
      exit 1
    fi
    sleep 2
  done
  echo "The app didn't come up in time. See: docker compose logs" >&2
  exit 1
}

start() {
  require_docker
  ensure_env
  require_free_ports
  compose up --build -d
  wait_until_up
  cat << 'EOF'

  App:       http://localhost:5173   (starts as Dr. Chen; switch personas in the header)
  API docs:  http://localhost:8000/docs

  Logs: docker compose logs -f api web    Stop: ./dev.sh stop
EOF
}

reset() {
  local count=10000
  if [[ "${1:-}" == "--count" ]]; then count="${2:?--count needs a number}"; fi
  require_docker
  ensure_env
  echo "Wiping the database and encryption keys together..."
  compose down
  docker volume rm -f patient-dashboard_pgdata patient-dashboard_keys > /dev/null
  require_free_ports
  SEED_COUNT="$count" compose up --build -d
  wait_until_up
  echo "Reset done: $count patients."
}

# Half the cores: the container shares them with the running API, database, and dev server,
# and Vitest otherwise starts a worker per core and its slowest tests run out of time.
frontend_tests() {
  compose run --build --rm --no-deps web \
    sh -c "bun install --frozen-lockfile && bun run check --maxWorkers=50%"
}

# The mock AI keeps runs deterministic and never spends a real key's quota. The API is recreated
# with it for the run, then put back on the .env provider whether the tests pass or not.
e2e_tests() {
  start
  local status=0
  SUMMARY_PROVIDER=mock compose up -d --force-recreate --no-deps --wait api
  # --no-deps: start() brought web up; resolving deps again would recreate the API without the mock.
  compose --profile test run --rm --no-deps e2e || status=$?
  compose up -d --force-recreate --no-deps --wait api
  return "$status"
}

run_tests() {
  require_docker
  local which="${1:-all}"
  compose up -d --wait db
  case "$which" in
    backend) compose run --build --rm --no-deps api pytest ;;
    privacy) compose run --build --rm --no-deps api pytest -m privacy ;;
    frontend) frontend_tests ;;
    e2e) e2e_tests ;;
    all)
      compose run --build --rm --no-deps api pytest
      frontend_tests
      ;;
    *)
      echo "Usage: ./dev.sh test [backend|frontend|e2e|privacy]" >&2
      exit 2
      ;;
  esac
}

proof() {
  require_docker
  compose up -d --wait db
  compose run --rm api python -m scripts.prove_encryption
}

case "${1:-start}" in
  start) start ;;
  reset) shift; reset "$@" ;;
  test) shift; run_tests "$@" ;;
  proof) proof ;;
  stop) compose stop ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
