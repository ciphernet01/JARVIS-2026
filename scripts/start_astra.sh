#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_HOST="${JARVIS_HOST:-127.0.0.1}"
BACKEND_PORT="${JARVIS_BACKEND_PORT:-8001}"
FRONTEND_PORT="${ASTRA_FRONTEND_PORT:-3000}"
LOG_DIR="${ASTRA_LOG_DIR:-/tmp/astra-runtime}"
VENV_CANDIDATES=(
  "$ROOT_DIR/.venv/bin/python"
  "$ROOT_DIR/.venv-linux/bin/python"
)
VENV_PYTHON=""

mkdir -p "$LOG_DIR" /tmp/matplotlib-astra

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Missing Linux virtualenv at $VENV_PYTHON"
  echo "Run: ./scripts/run_linux_tests.sh"
  exit 1
fi

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "Missing frontend dependencies. Run: cd frontend && npm install"
  exit 1
fi

for candidate in "${VENV_CANDIDATES[@]}"; do
  if [ -x "$candidate" ]; then
    VENV_PYTHON="$candidate"
    break
  fi
done

if [ -z "$VENV_PYTHON" ]; then
  echo "Missing Python virtualenv. Expected one of:"
  printf '  %s\n' "${VENV_CANDIDATES[@]}"
  exit 1
fi

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is online: $url"
      return 0
    fi
    sleep 1
  done

  echo "$name did not become ready: $url"
  return 1
}

trap cleanup EXIT INT TERM

echo "Starting A.S.T.R.A backend on http://$BACKEND_HOST:$BACKEND_PORT"
(
  cd "$ROOT_DIR"
  JARVIS_HOST="$BACKEND_HOST" \
  JARVIS_BACKEND_PORT="$BACKEND_PORT" \
  MPLCONFIGDIR=/tmp/matplotlib-astra \
  "$VENV_PYTHON" backend/server.py
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID="$!"

wait_for_url "http://$BACKEND_HOST:$BACKEND_PORT/api/health" "Backend" 90 || {
  tail -80 "$BACKEND_LOG"
  exit 1
}

echo "Starting A.S.T.R.A interface on http://localhost:$FRONTEND_PORT"
(
  cd "$ROOT_DIR/frontend"
  DISABLE_ESLINT_PLUGIN=true \
  PORT="$FRONTEND_PORT" \
  REACT_APP_BACKEND_URL="http://$BACKEND_HOST:$BACKEND_PORT" \
  BROWSER=none \
  npm start
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID="$!"

wait_for_url "http://127.0.0.1:$FRONTEND_PORT" "Frontend" 90 || {
  tail -80 "$FRONTEND_LOG"
  exit 1
}

cat <<EOF

A.S.T.R.A is ready for operation.
Frontend: http://localhost:$FRONTEND_PORT
Backend:  http://$BACKEND_HOST:$BACKEND_PORT

Logs:
Backend:  $BACKEND_LOG
Frontend: $FRONTEND_LOG

Press Ctrl+C to stop both services.
EOF

wait
