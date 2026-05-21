#!/usr/bin/env bash
set -euo pipefail

# Linux test runner: creates venv, installs linux-specific deps, runs pytest
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-linux"

echo "Using project root: $ROOT_DIR"

if [ -d "$VENV_DIR" ]; then
  echo "Reusing existing venv: $VENV_DIR"
else
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

echo "Installing Linux requirements..."
python -m pip install -r "$ROOT_DIR/requirements.linux.txt" -r "$ROOT_DIR/backend/requirements.txt"

echo "Running pytest..."
pytest -q

echo "Tests complete"
