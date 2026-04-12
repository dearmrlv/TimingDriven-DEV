#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
INSTALL_DIR=${INSTALL_DIR:-"$ROOT_DIR/install"}
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}
METHOD=efficient_tdp
CONFIG_SUBDIR=iccad2015.pin2pin
DEFAULT_CASES=(superblue1 superblue16 superblue18)
ALL_CASES=(superblue1 superblue3 superblue4 superblue5 superblue7 superblue10 superblue16 superblue18)

if [ ! -x "$VENV_PYTHON" ]; then
  printf 'Expected Python environment at %s. Run scripts/setup_env.sh first.\n' "$VENV_PYTHON" >&2
  exit 1
fi

if [ ! -f "$INSTALL_DIR/dreamplace/Placer.py" ]; then
  printf 'Expected installed runtime at %s. Run scripts/build.sh first.\n' "$INSTALL_DIR" >&2
  exit 1
fi

TORCH_RUNTIME_LIBS=$(
  "$VENV_PYTHON" -c "import pathlib, torch; root = pathlib.Path(torch.__file__).resolve().parent.parent; paths = [pathlib.Path(torch.__file__).resolve().parent / 'lib']; paths.extend(sorted(p for p in (root / 'nvidia').glob('*/lib') if p.is_dir())); print(':'.join(str(p) for p in paths))"
)
export LD_LIBRARY_PATH="$TORCH_RUNTIME_LIBS:${LD_LIBRARY_PATH:-}"

cases=()
if [ "$#" -eq 0 ]; then
  cases=("${DEFAULT_CASES[@]}")
elif [ "$1" = "--all" ]; then
  cases=("${ALL_CASES[@]}")
else
  cases=("$@")
fi

mkdir -p "$ROOT_DIR/logs/$METHOD" "$ROOT_DIR/results/baselines/$METHOD"
git_commit=$(git rev-parse HEAD)

for case_name in "${cases[@]}"; do
  source_config="$INSTALL_DIR/test/$CONFIG_SUBDIR/${case_name}.json"
  run_dir="$ROOT_DIR/results/baselines/$METHOD/$case_name"
  runtime_config="$run_dir/config.json"
  log_file="$ROOT_DIR/logs/$METHOD/${case_name}.log"
  command_file="$run_dir/command.txt"
  git_file="$run_dir/git_commit.txt"

  if [ ! -f "$source_config" ]; then
    printf 'Missing config %s\n' "$source_config" >&2
    exit 1
  fi

  mkdir -p "$run_dir"

  "$VENV_PYTHON" - "$source_config" "$runtime_config" "$ROOT_DIR/results/baselines/$METHOD" <<'PY'
import json
import pathlib
import sys

source_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
result_dir = pathlib.Path(sys.argv[3]).resolve()

with source_path.open() as f:
    data = json.load(f)

data["result_dir"] = str(result_dir)
data["detailed_place_engine"] = ""
data["gpu"] = 1

runtime_path.parent.mkdir(parents=True, exist_ok=True)
with runtime_path.open("w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

  printf '%s\n' "$git_commit" > "$git_file"
  printf '%s\n' "$VENV_PYTHON dreamplace/Placer.py $runtime_config" > "$command_file"

  (
    cd "$INSTALL_DIR"
    "$VENV_PYTHON" -c 'import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)'
    /usr/bin/time -f 'wall_clock_seconds %e' "$VENV_PYTHON" dreamplace/Placer.py "$runtime_config"
  ) 2>&1 | tee "$log_file"

  "$ROOT_DIR/scripts/run_eval.sh" "$METHOD" "$case_name"
done
