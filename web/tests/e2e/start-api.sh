#!/usr/bin/env bash
# Start a throwaway Boughtsafe API seeded with the test fixtures (no network needed).
set -euo pipefail
cd "$(dirname "$0")/../../../server"
DB="${E2E_DB:-${TMPDIR:-/tmp}/boughtsafe-e2e.db}"
BIN="${BOUGHTSAFE_BIN:-.venv/bin/boughtsafe}"
rm -f "$DB" "$DB-wal" "$DB-shm"
export BOUGHTSAFE_DATABASE_URL="sqlite:///$DB"
export BOUGHTSAFE_OFF_ENABLED=false
export BOUGHTSAFE_CORS_ORIGINS='["http://localhost:4173"]'
export BOUGHTSAFE_BUILD_NUMBER="${BUILD_NUMBER:-e2e}"
"$BIN" migrate
"$BIN" seed tests/fixtures/recalls.json
exec "$BIN" serve --host 127.0.0.1 --port "${E2E_API_PORT:-8000}" --no-migrate
