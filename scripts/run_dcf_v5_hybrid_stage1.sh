#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
INSTALL_DIR=${INSTALL_DIR:-"$ROOT_DIR/install"}
CONFIG_ROOT=${CONFIG_ROOT:-"$ROOT_DIR/test"}
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}
OUTPUT_TAG=${OUTPUT_TAG:-"dcf_v5_hybrid_stage1"}
RUN_LABEL=${RUN_LABEL:-""}
DEFAULT_CASES=(superblue16 superblue3 superblue18)
METHOD_KEYS=${METHOD_KEYS:-"dcf_v3b,dcf_v4,dcf_v5_hybrid_l010,dcf_v5_hybrid_l020,dcf_v5_hybrid_l030"}
DCF_HYBRID_DEBUG=${DCF_HYBRID_DEBUG:-0}
DCF_HYBRID_DEBUG_DUMP_FIRST_TIMING_STEP_ONLY=${DCF_HYBRID_DEBUG_DUMP_FIRST_TIMING_STEP_ONLY:-0}
DCF_HYBRID_DEBUG_DUMP_DIR=${DCF_HYBRID_DEBUG_DUMP_DIR:-"$ROOT_DIR/results/hybrid_debug"}
DCF_DIAG_FIRST_STEP_ONLY=${DCF_DIAG_FIRST_STEP_ONLY:-0}
METHOD_SPECS=(
  "dcf_v3b|DCF v3b|dcf|v3b|"
  "dcf_v4|DCF v4|dcf|v4|"
  "dcf_v5_hybrid_l010|DCF v5 hybrid|dcf_hybrid||0.10"
  "dcf_v5_hybrid_l020|DCF v5 hybrid|dcf_hybrid||0.20"
  "dcf_v5_hybrid_l030|DCF v5 hybrid|dcf_hybrid||0.30"
)

method_selected() {
  local method_key="$1"
  [[ ",${METHOD_KEYS}," == *",${method_key},"* ]]
}

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

git_commit=$(git rev-parse HEAD)
result_root="$ROOT_DIR/results/$OUTPUT_TAG"
log_root="$ROOT_DIR/logs/$OUTPUT_TAG"

cases=()
if [ "$#" -eq 0 ]; then
  cases=("${DEFAULT_CASES[@]}")
else
  cases=("$@")
fi

for case_name in "${cases[@]}"; do
  source_config="$CONFIG_ROOT/iccad2015.pin2pin/${case_name}.json"
  if [ ! -f "$source_config" ]; then
    printf 'Missing base config %s\n' "$source_config" >&2
    exit 1
  fi

  for spec in "${METHOD_SPECS[@]}"; do
    IFS='|' read -r method_key method_label scheme version hybrid_lambda <<< "$spec"
    if ! method_selected "$method_key"; then
      continue
    fi

    run_dir="$result_root/$method_key/$case_name"
    method_result_dir="$result_root/$method_key"
    runtime_config="$run_dir/config.json"
    log_dir="$log_root/$method_key"
    log_file="$log_dir/${case_name}.log"
    if [ -n "$RUN_LABEL" ]; then
      log_file="$log_dir/${case_name}.${RUN_LABEL}.log"
    fi
    command_file="$run_dir/command.txt"
    git_file="$run_dir/git_commit.txt"
    diagnostics_root="$result_root/diagnostics"

    mkdir -p "$run_dir" "$log_dir"

    "$VENV_PYTHON" - "$source_config" "$runtime_config" "$method_result_dir" "$diagnostics_root" "$method_key" "$scheme" "$version" "$hybrid_lambda" "$RUN_LABEL" "$DCF_HYBRID_DEBUG" "$DCF_HYBRID_DEBUG_DUMP_FIRST_TIMING_STEP_ONLY" "$DCF_HYBRID_DEBUG_DUMP_DIR" "$DCF_DIAG_FIRST_STEP_ONLY" <<'PY'
import json
import pathlib
import sys

source_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
result_dir = pathlib.Path(sys.argv[3]).resolve()
diagnostics_root = pathlib.Path(sys.argv[4]).resolve()
method_key = sys.argv[5]
scheme = sys.argv[6]
version = sys.argv[7]
hybrid_lambda = sys.argv[8]
run_label = sys.argv[9]
hybrid_debug = bool(int(sys.argv[10]))
hybrid_debug_first_step_only = bool(int(sys.argv[11]))
hybrid_debug_dump_dir = sys.argv[12]
diag_first_step_only = bool(int(sys.argv[13]))

with source_path.open() as f:
    data = json.load(f)

data["result_dir"] = str(result_dir)
data["detailed_place_engine"] = ""
data["gpu"] = 1
data["net_weighting_scheme"] = scheme
data["enable_net_weighting"] = 1
data["pin2pin_net_weighting"] = 1
data["enable_dcf"] = 1
if version:
    data["dcf_version"] = version
if hybrid_lambda:
    data["dcf_hybrid_lambda"] = float(hybrid_lambda)
data["enable_dcf_diagnostics"] = 1
data["dcf_diag_dump_dir"] = str(diagnostics_root)
data["dcf_diag_dump_first_timing_step_only"] = 1 if diag_first_step_only else 0
data["dcf_diag_dump_step_ids"] = []
data["dcf_diag_save_snapshot_step_ids"] = []
data["dcf_diag_replay_snapshot_dir"] = ""
data["dcf_diag_stop_after_last_dump_step"] = 0
data["dcf_diag_timing_steps_filename"] = "timing_steps.jsonl"
data["dcf_diag_dump_pair_limit"] = 0
data["dcf_diag_dump_state_stats"] = 0
data["dcf_diag_dump_topk"] = 1000
data["dcf_diag_dump_term_grad_norms"] = 0
data["dcf_diag_scheme_tag"] = method_key if not run_label else f"{method_key}_{run_label}"
data["dcf_hybrid_debug"] = 1 if hybrid_debug else 0
data["dcf_hybrid_debug_dump_first_timing_step_only"] = 1 if hybrid_debug_first_step_only else 0
data["dcf_hybrid_debug_dump_dir"] = hybrid_debug_dump_dir

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
      --method-key "$method_key" \
      --variant "${version:-$scheme}" \
      --beta "$hybrid_lambda" \
      --case "$case_name" \
      --run-dir "$run_dir" \
      --log "$log_file" \
      --output-tag "$OUTPUT_TAG" \
      --run-label "$RUN_LABEL" \
      --output "$run_dir/metrics.json"
  done
done
