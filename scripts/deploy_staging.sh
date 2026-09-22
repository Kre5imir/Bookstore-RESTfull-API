#!/usr/bin/env bash
# Prepare a local staging database, boot the API, and require a healthy response.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAGING_DIR="${STAGING_DIR:-$ROOT/.staging}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
BASE_URL="http://${HOST}:${PORT}"
LOG_FILE="${TMPDIR:-/tmp}/bookstore-staging.log"
mkdir -p "$STAGING_DIR"

export DJANGO_DEBUG=false
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-127.0.0.1,localhost}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-staging-only-secret-key-not-for-production-use}"
export BOOKSTORE_DB_PATH="$STAGING_DIR/db.sqlite3"

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat >"$STAGING_DIR/deploy-manifest.json" <<EOF
{
  "service": "readify-bookstore-api",
  "version": "1.0.0",
  "git_sha": "${GIT_SHA}",
  "deployed_at": "${DEPLOYED_AT}",
  "database": "${BOOKSTORE_DB_PATH}"
}
EOF

python3 manage.py check --deploy
python3 manage.py migrate --noinput

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

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
  echo "Staging health check failed. Log follows:" >&2
  cat "$LOG_FILE" >&2
  exit 1
fi

echo "Staging deploy is healthy at ${BASE_URL}"
echo "Manifest written to ${STAGING_DIR}/deploy-manifest.json"
