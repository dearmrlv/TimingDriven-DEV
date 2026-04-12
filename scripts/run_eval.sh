#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}

if [ "$#" -ne 2 ]; then
  printf 'Usage: %s <method> <case>\n' "$0" >&2
  exit 1
fi

"$VENV_PYTHON" "$ROOT_DIR/scripts/collect_results.py" --method "$1" --case "$2" --write-json
