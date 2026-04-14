#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
INSTALL_DIR=${INSTALL_DIR:-"$ROOT_DIR/install"}
CONFIG_ROOT=${CONFIG_ROOT:-"$ROOT_DIR/test"}
VENV_PYTHON=${VENV_PYTHON:-"$ROOT_DIR/.venv/bin/python"}
OUTPUT_TAG=${OUTPUT_TAG:-"dcf_v3"}
RUN_LABEL=${RUN_LABEL:-""}
DEFAULT_CASES=(superblue18 superblue16)
METHOD_KEYS=${METHOD_KEYS:-"dcf_v1,dcf_v3b,dcf_v3c_b005,dcf_v3c_b010,dcf_v3c_b015,dcf_v3c_b020,dcf_v3c_b025"}
METHOD_SPECS=(
  "dcf_v1|DCF v1|v1||iccad2015.dcf|{case}.json"
  "dcf_v3a|DCF v3a|v3a||iccad2015.dcfv3|{case}.v3a.json"
  "dcf_v3b|DCF v3b|v3b||iccad2015.dcfv3|{case}.v3b.json"
  "dcf_v3c|DCF v3c|v3c|0.25|iccad2015.dcfv3|{case}.v3c.json"
  "dcf_v3c_b005|DCF v3c|v3c|0.05|iccad2015.dcfv3|{case}.v3c.b005.json"
  "dcf_v3c_b010|DCF v3c|v3c|0.10|iccad2015.dcfv3|{case}.v3c.b010.json"
  "dcf_v3c_b015|DCF v3c|v3c|0.15|iccad2015.dcfv3|{case}.v3c.b015.json"
  "dcf_v3c_b020|DCF v3c|v3c|0.20|iccad2015.dcfv3|{case}.v3c.b020.json"
  "dcf_v3c_b025|DCF v3c|v3c|0.25|iccad2015.dcfv3|{case}.v3c.b025.json"
)

method_selected() {
  local method_key="$1"
  case ",${METHOD_KEYS}," in
    *,"${method_key}",*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
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

cases=()
if [ "$#" -eq 0 ]; then
  cases=("${DEFAULT_CASES[@]}")
else
  cases=("$@")
fi

git_commit=$(git rev-parse HEAD)
result_root="$ROOT_DIR/results/$OUTPUT_TAG"
log_root="$ROOT_DIR/logs/$OUTPUT_TAG"

for case_name in "${cases[@]}"; do
  for spec in "${METHOD_SPECS[@]}"; do
    IFS='|' read -r method_key method_label variant beta config_subdir config_template <<< "$spec"
    if ! method_selected "$method_key"; then
      continue
    fi

    config_name="${config_template//\{case\}/$case_name}"

    source_config="$CONFIG_ROOT/$config_subdir/$config_name"
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

    if [ ! -f "$source_config" ]; then
      printf 'Missing config %s\n' "$source_config" >&2
      exit 1
    fi

    mkdir -p "$run_dir" "$log_dir"

    "$VENV_PYTHON" - "$source_config" "$runtime_config" "$method_result_dir" "$diagnostics_root" "$method_key" "$RUN_LABEL" <<'PY'
import json
import pathlib
import sys

source_path = pathlib.Path(sys.argv[1])
runtime_path = pathlib.Path(sys.argv[2])
result_dir = pathlib.Path(sys.argv[3]).resolve()
diagnostics_root = pathlib.Path(sys.argv[4]).resolve()
method_key = sys.argv[5]
run_label = sys.argv[6]

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
data["dcf_diag_scheme_tag"] = method_key if not run_label else f"{method_key}_{run_label}"

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
      --variant "$variant" \
      --beta "$beta" \
      --case "$case_name" \
      --run-dir "$run_dir" \
      --log "$log_file" \
      --output-tag "$OUTPUT_TAG" \
      --run-label "$RUN_LABEL" \
      --output "$run_dir/metrics.json"
  done
done
