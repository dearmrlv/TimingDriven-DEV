#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
INSTALL_DIR=${INSTALL_DIR:-"$ROOT_DIR/install"}
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}
DEFAULT_CASES=(superblue18 superblue16)
VARIANTS=(v1 v3a v3b v3c)

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
else
  cases=("$@")
fi

git_commit=$(git rev-parse HEAD)

for case_name in "${cases[@]}"; do
  for variant in "${VARIANTS[@]}"; do
    method_key="dcf_${variant}"
    method_label="DCF ${variant}"
    config_subdir="iccad2015.dcf"
    config_name="${case_name}.json"
    if [ "$variant" != "v1" ]; then
      config_subdir="iccad2015.dcfv3"
      config_name="${case_name}.${variant}.json"
    fi

    source_config="$INSTALL_DIR/test/$config_subdir/$config_name"
    run_dir="$ROOT_DIR/results/dcf_v3/$method_key/$case_name"
    method_result_dir="$ROOT_DIR/results/dcf_v3/$method_key"
    runtime_config="$run_dir/config.json"
    log_dir="$ROOT_DIR/logs/dcf_v3/$method_key"
    log_file="$log_dir/${case_name}.log"
    command_file="$run_dir/command.txt"
    git_file="$run_dir/git_commit.txt"
    diagnostics_root="$ROOT_DIR/results/dcf_v3/diagnostics"

    if [ ! -f "$source_config" ]; then
      printf 'Missing config %s\n' "$source_config" >&2
      exit 1
    fi

    mkdir -p "$run_dir" "$log_dir"

    "$VENV_PYTHON" - "$source_config" "$runtime_config" "$method_result_dir" "$diagnostics_root" "$method_key" <<'PY'
import json
import pathlib
import sys

source_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
result_dir = pathlib.Path(sys.argv[3]).resolve()
diagnostics_root = pathlib.Path(sys.argv[4]).resolve()
method_key = sys.argv[5]

with source_path.open() as f:
    data = json.load(f)

data["result_dir"] = str(result_dir)
data["detailed_place_engine"] = ""
data["gpu"] = 1
data["enable_dcf_diagnostics"] = 1
data["dcf_diag_dump_dir"] = str(diagnostics_root)
data["dcf_diag_dump_first_timing_step_only"] = 0
data["dcf_diag_dump_step_ids"] = []
data["dcf_diag_save_snapshot_step_ids"] = []
data["dcf_diag_replay_snapshot_dir"] = ""
data["dcf_diag_stop_after_last_dump_step"] = 0
data["dcf_diag_timing_steps_filename"] = "timing_steps.jsonl"
data["dcf_diag_dump_pair_limit"] = 0
data["dcf_diag_dump_state_stats"] = 0
data["dcf_diag_dump_topk"] = 1000
data["dcf_diag_dump_term_grad_norms"] = 0
data["dcf_diag_scheme_tag"] = method_key

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

    "$VENV_PYTHON" "$ROOT_DIR/scripts/collect_experiment_metrics.py" \
      --method "$method_label" \
      --case "$case_name" \
      --run-dir "$run_dir" \
      --log "$log_file" \
      --output "$run_dir/metrics.json"
  done
done
