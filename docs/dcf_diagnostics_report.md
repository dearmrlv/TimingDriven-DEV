# DCF Diagnostics Report

This branch adds diagnostics-only instrumentation for DCF v1 and records the first data dump runs used to compare `dcf` against `pin2pin` on matched placement states.

## What Was Added

- default-off diagnostics config fields in `dreamplace/params.json`
- a Python diagnostics manager in `dreamplace/dcf_diagnostics.py`
- timing-step summary dumping in `dreamplace/NonLinearPlace.py`
- one-shot objective-term gradient norm snapshots in `dreamplace/PlaceObj.py`
- timing diagnostics plumbing in:
  - `dreamplace/BasicPlace.py`
  - `dreamplace/ops/timing/timing.py`
  - `dreamplace/ops/timing/src/timing_cpp.h`
  - `dreamplace/ops/timing/src/timing_cpp.cpp`
  - `dreamplace/ops/timing/src/net_weighting_scheme.h`
- matched diagnostics config family in `test/iccad2015.diagnostics/`
- comparison helper script in `scripts/compare_pair_dumps.py`
- diagnostics runner script in `scripts/run_dcf_diagnostics.sh`
- planning note in `docs/dcf_diagnostics_plan.md`

## Files Changed

- `docs/dcf_diagnostics_plan.md`
- `docs/dcf_diagnostics_report.md`
- `dreamplace/params.json`
- `dreamplace/BasicPlace.py`
- `dreamplace/NonLinearPlace.py`
- `dreamplace/PlaceObj.py`
- `dreamplace/dcf_diagnostics.py`
- `dreamplace/ops/timing/timing.py`
- `dreamplace/ops/timing/src/timing_cpp.h`
- `dreamplace/ops/timing/src/timing_cpp.cpp`
- `dreamplace/ops/timing/src/net_weighting_scheme.h`
- `test/CMakeLists.txt`
- `test/iccad2015.diagnostics/README.md`
- `test/iccad2015.diagnostics/superblue18.pin2pin.json`
- `test/iccad2015.diagnostics/superblue18.dcf.json`
- `test/iccad2015.diagnostics/superblue16.pin2pin.json`
- `test/iccad2015.diagnostics/superblue16.dcf.json`
- `scripts/compare_pair_dumps.py`
- `scripts/run_dcf_diagnostics.sh`

## Runs Executed

Matched diagnostics configs were used so that `pin2pin` and `dcf` share the same placement hyperparameters within each case.

Executed commands:

- `bash scripts/run_dcf_diagnostics.sh first-step superblue18 pin2pin`
- `bash scripts/run_dcf_diagnostics.sh first-step superblue18 dcf`
- `python scripts/compare_pair_dumps.py --dcf results/diagnostics/superblue18/dcf/step_001/exported_pairs.csv.gz --pin2pin results/diagnostics/superblue18/pin2pin/step_001/exported_pairs.csv.gz --output results/diagnostics/superblue18/compare_dcf_vs_pin2pin_step_001.json`
- `bash scripts/run_dcf_diagnostics.sh first-step superblue16 pin2pin`
- `bash scripts/run_dcf_diagnostics.sh first-step superblue16 dcf`
- `python scripts/compare_pair_dumps.py --dcf results/diagnostics/superblue16/dcf/step_001/exported_pairs.csv.gz --pin2pin results/diagnostics/superblue16/pin2pin/step_001/exported_pairs.csv.gz --output results/diagnostics/superblue16/compare_dcf_vs_pin2pin_step_001.json`
- `bash scripts/run_dcf_diagnostics.sh full-run superblue18 pin2pin`
- `bash scripts/run_dcf_diagnostics.sh full-run superblue18 dcf`
- `bash scripts/run_dcf_diagnostics.sh full-run superblue16 pin2pin`
- `bash scripts/run_dcf_diagnostics.sh full-run superblue16 dcf`

## Outputs Produced

Top-level diagnostics root:

- `results/diagnostics/`

Case-level comparison reports:

- `results/diagnostics/superblue18/compare_dcf_vs_pin2pin_step_001.json`
- `results/diagnostics/superblue16/compare_dcf_vs_pin2pin_step_001.json`

Per-scheme outputs were produced under:

- `results/diagnostics/superblue18/pin2pin/`
- `results/diagnostics/superblue18/dcf/`
- `results/diagnostics/superblue16/pin2pin/`
- `results/diagnostics/superblue16/dcf/`

Per-scheme contents include:

- `config_used.json`
- `run_metadata.json`
- `runtime_config.json`
- `timing_steps.jsonl`
- `step_001/exported_pairs.csv.gz`

DCF step payloads additionally include:

- `step_001/state_stats.csv.gz`
- `step_001/utility_summary.json`
- `step_001/objective_term_norms.json`

Pin2pin step payloads include:

- `step_001/objective_term_norms.json`

Timing-step summary row counts from the full-run summaries:

- `superblue18/pin2pin/timing_steps.jsonl`: 16 rows
- `superblue18/dcf/timing_steps.jsonl`: 14 rows
- `superblue16/pin2pin/timing_steps.jsonl`: 15 rows
- `superblue16/dcf/timing_steps.jsonl`: 33 rows

Same-state first-step fingerprints recorded in `timing_steps.jsonl`:

- `superblue18`
  - `pin2pin`: `07830ad38bd2bd9b`
  - `dcf`: `07830ad38bd2bd9b`
- `superblue16`
  - `pin2pin`: `b9f515faca568f7a`
  - `dcf`: `b9f515faca568f7a`

## Instrumentation Limitations

- DCF state dumps are mapped onto DreamPlace pin IDs through `pin_name2id_map`. Any state rows that do not map back into the placement DB pin array are skipped during CSV writing.
- Heavy per-step dumps are currently designated to the first timing step. `timing_steps.jsonl` still records every timing update in the run.
- Objective-term gradient norms are one-shot snapshots taken at the designated timing step only.
- Comparison JSON reports are generated from the exported pair dumps, not from internal OpenTimer path objects.
