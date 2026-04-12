#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
PYTHON_VERSION=${PYTHON_VERSION:-3.11}
VENV_DIR=${VENV_DIR:-"$ROOT_DIR/.venv"}
TORCH_VERSION=${TORCH_VERSION:-2.7.1}
TORCH_INDEX_URL=${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu126}

if ! command -v uv >/dev/null 2>&1; then
  printf 'uv is required but was not found on PATH.\n' >&2
  exit 1
fi

uv python install "$PYTHON_VERSION"
uv venv --python "$PYTHON_VERSION" "$VENV_DIR"
uv sync --directory "$ROOT_DIR" --python "$VENV_DIR/bin/python"
uv pip install --python "$VENV_DIR/bin/python" --index-url "$TORCH_INDEX_URL" "torch==${TORCH_VERSION}"

"$VENV_DIR/bin/python" -c 'import sys; import torch; print(f"python={sys.version.split()[0]}"); print(f"torch={torch.__version__}"); print(f"torch_cuda={torch.version.cuda}"); print(f"cuda_available={int(torch.cuda.is_available())}")'
