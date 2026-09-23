#!/usr/bin/env bash
# Boot the API and run the Postman collection with Newman.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${TMPDIR:-/tmp}/bookstore-api-tests.log"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

python3 manage.py migrate --noinput
python3 manage.py runserver --noreload "${HOST}:${PORT}" >"$LOG_FILE" 2>&1 &
SERVER_PID=$!

ready=0
for _ in $(seq 1 30); do
  if curl -sf "${BASE_URL}/health" >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" -ne 1 ]]; then
  echo "API server did not become healthy. Log follows:" >&2
  cat "$LOG_FILE" >&2
  exit 1
fi

npx --yes newman run postman/bookstore.postman_collection.json \
  -e postman/bookstore.postman_environment.json \
  --env-var "baseUrl=${BASE_URL}"
