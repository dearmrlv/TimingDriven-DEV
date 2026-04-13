#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
INSTALL_DIR=${INSTALL_DIR:-"$ROOT_DIR/install"}
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}
CONFIG_SUBDIR=iccad2015.diagnostics

if [ "$#" -ne 3 ]; then
  printf 'Usage: %s <first-step|full-run> <case> <pin2pin|dcf>\n' "$0" >&2
  exit 1
fi

MODE=$1
CASE_NAME=$2
SCHEME=$3

if [ ! -x "$VENV_PYTHON" ]; then
  printf 'Expected Python environment at %s. Run scripts/setup_env.sh first.\n' "$VENV_PYTHON" >&2
  exit 1
fi

if [ ! -f "$INSTALL_DIR/dreamplace/Placer.py" ]; then
  printf 'Expected installed runtime at %s. Run scripts/build.sh first.\n' "$INSTALL_DIR" >&2
  exit 1
fi

SOURCE_CONFIG="$INSTALL_DIR/test/$CONFIG_SUBDIR/${CASE_NAME}.${SCHEME}.json"
if [ ! -f "$SOURCE_CONFIG" ]; then
  printf 'Missing config %s\n' "$SOURCE_CONFIG" >&2
  exit 1
fi

TORCH_RUNTIME_LIBS=$(
  "$VENV_PYTHON" -c "import pathlib, torch; root = pathlib.Path(torch.__file__).resolve().parent.parent; paths = [pathlib.Path(torch.__file__).resolve().parent / 'lib']; paths.extend(sorted(p for p in (root / 'nvidia').glob('*/lib') if p.is_dir())); print(':'.join(str(p) for p in paths))"
)
export LD_LIBRARY_PATH="$TORCH_RUNTIME_LIBS:${LD_LIBRARY_PATH:-}"

RUN_ROOT="$ROOT_DIR/results/diagnostics/$CASE_NAME/$SCHEME"
RUNTIME_RESULT_DIR="$ROOT_DIR/results/diagnostics_runtime/$CASE_NAME/$SCHEME"
RUNTIME_CONFIG="$RUN_ROOT/runtime_config.json"
LOG_DIR="$ROOT_DIR/logs/diagnostics"
LOG_FILE="$LOG_DIR/${CASE_NAME}.${SCHEME}.${MODE}.log"
mkdir -p "$RUN_ROOT" "$RUNTIME_RESULT_DIR" "$LOG_DIR"

"$VENV_PYTHON" - "$SOURCE_CONFIG" "$RUNTIME_CONFIG" "$RUNTIME_RESULT_DIR" "$ROOT_DIR/results/diagnostics" "$CASE_NAME" "$SCHEME" "$MODE" <<'PY'
import json
import pathlib
import sys

source_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
result_dir = pathlib.Path(sys.argv[3]).resolve()
diag_root = pathlib.Path(sys.argv[4]).resolve()
case_name = sys.argv[5]
scheme = sys.argv[6]
mode = sys.argv[7]

with source_path.open() as f:
    data = json.load(f)

data["result_dir"] = str(result_dir)
data["detailed_place_engine"] = ""
data["gpu"] = 1
data["enable_dcf_diagnostics"] = 1
data["dcf_diag_dump_dir"] = str(diag_root)
data["dcf_diag_dump_first_timing_step_only"] = 1 if mode == "first-step" else 0
data["dcf_diag_dump_pair_limit"] = 0
data["dcf_diag_dump_state_stats"] = 1 if scheme == "dcf" else 0
data["dcf_diag_dump_topk"] = 1000
data["dcf_diag_dump_term_grad_norms"] = 1
data["dcf_diag_case_tag"] = case_name
data["dcf_diag_scheme_tag"] = scheme

runtime_path.parent.mkdir(parents=True, exist_ok=True)
with runtime_path.open("w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

(
  cd "$INSTALL_DIR"
  "$VENV_PYTHON" -c 'import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)'
  /usr/bin/time -f 'wall_clock_seconds %e' "$VENV_PYTHON" dreamplace/Placer.py "$RUNTIME_CONFIG"
) 2>&1 | tee "$LOG_FILE"
