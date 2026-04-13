# DCF Diagnostics Plan

This branch adds diagnostics-only instrumentation for DCF v1 without changing timing-weight semantics or the placement objective.

## Scope

- Keep DREAMPlace 4.0, Efficient-TDP, and DCF runs working as they do today when diagnostics are disabled.
- Put all diagnostics behind config flags, default-off.
- Reuse the existing timing-update cadence and the existing pin-pair export path.
- Make same-state comparison between `pin2pin` and `dcf` possible by using matched diagnostic configs that differ only in timing-weighting fields.

## Timing-Step Orchestration

The timing update already has one clean control point in `dreamplace/NonLinearPlace.py` inside the global placement loop.

Current order:

1. `timing_op(pos_cpu)` updates RC trees for the current placement.
2. `timing_op.timer.update_timing()` runs STA.
3. `timing_op.update_net_weights(...)` runs the selected weighting scheme.
4. `placedb.pin2pin_net_weight` is flattened into the device pair tensors.

Diagnostics will be orchestrated around that block.

Planned additions in `dreamplace/NonLinearPlace.py`:

- maintain a `timing_step_id` counter
- compute a deterministic `position_fingerprint` from the CPU position tensor just before the timing update
- measure total timing-update runtime around RC update, STA, timing-weight update, and pair transfer
- append one JSON row per timing step to `timing_steps.jsonl`
- dump the designated step payload into `results/diagnostics/<case>/<scheme>/step_<timing_step_id>/...`
- support first-timing-step-only diagnostics mode, including early exit after the first timing update

## Config Plumbing

Diagnostics config is added in `dreamplace/params.json` and passed through:

- `dreamplace/BasicPlace.py` into `timing.TimingOpt`
- `dreamplace/ops/timing/timing.py` into the C++ timing update bridge

The new flags remain harmless when disabled.

## Per-Timing-Step Summary

Summary rows will be written from Python in `NonLinearPlace.py` because that layer has direct access to:

- global placement iteration number
- timing-step count
- final exported pair dictionary
- current position tensor
- TNS / WNS / NVP after STA
- total runtime of the whole timing-update block

Fields sourced in Python:

- `case_name`
- `scheme_name`
- `gp_iter`
- `timing_step_id`
- `start_iter`
- `TNS`
- `WNS`
- `NVP`
- `exported_pair_count`
- `total_exported_weight_mass`
- `top1_weight_mass_ratio`
- `top5_weight_mass_ratio`
- `average_exported_pair_length`
- `median_exported_pair_length`
- `max_exported_pair_length`
- `timing_update_total_runtime_sec`
- `position_fingerprint`

Fields sourced from the DCF payload returned by the timing C++ bridge:

- `dcf_pass_runtime_sec`
- `arcs_with_nonzero_mass`
- `failing_endpoints_injected`

## Exported Pair Dump

All schemes already converge onto `placedb.pin2pin_net_weight`, so exported pair dumping should stay on that shared path.

Plan:

- `NonLinearPlace.py` calls a diagnostics helper after `placedb.pin2pin_net_weight` is finalized for the step
- for `pin2pin`, the helper derives rows directly from the exported pair dictionary
- for `dcf`, the helper merges the exported pair dictionary with DCF-specific per-pair diagnostics returned by the C++ layer

Common fields for all schemes:

- `timing_step_id`
- `gp_iter`
- `src_pin_id`
- `dst_pin_id`
- `src_pin_name`
- `dst_pin_name`
- `current_manhattan_length`
- `final_exported_weight`

Additional DCF-only fields returned by C++ on the designated dump step:

- `hist_bin0`
- `hist_bin1`
- `hist_bin2`
- `hist_bin3`
- `M`
- `S`
- `T`
- `utility_U`
- `length_eta`
- `mapped_weight_before_ema`
- `final_exported_weight_after_ema`

The dump is written as `exported_pairs.csv.gz` under the step directory.

`dcf_diag_dump_pair_limit` applies only to the heavy per-step pair dump. Summary statistics still use the full exported pair set.

## DCF Internal Utility Decomposition

The DCF implementation in `dreamplace/ops/timing/src/net_weighting_scheme.h` already computes the needed internal terms while converting reverse-propagated mass into exported pin-pair weights.

Instrumentation should stay local to that implementation.

Planned DCF payload contents:

- per-pair tensors for the designated dump step
- aggregate utility summary over all exported DCF pairs

The utility summary will include:

- quantiles for `M`, `S`, `T`, `eta`, and `mapped_weight_before_ema`
- Pearson correlation of final weight with `eta`, `M`, `S`, and `T`
- Spearman correlation of final weight with `eta`, `M`, `S`, and `T`

This keeps DCF internals close to the code that actually computes them and avoids re-deriving DCF terms in Python.

## Attribution Sharpness Stats

Attribution sharpness must be captured inside `NetWeightingScheme::DCF`, because the reverse pass already has the state-level candidate set and attribution probabilities.

For each active timing state `(pin, rise/fall)` with nonzero mass, collect:

- `pin_id`
- `rf`
- `node_mass_total`
- `num_candidate_predecessors`
- `max_prob`
- `top1_prob`
- `top3_prob_sum`
- `attribution_entropy`
- `outgoing_mass_total`
- `incoming_mass_total`

The C++ layer will return compact tensors for these state rows on the designated dump step when `dcf_diag_dump_state_stats` is enabled.

Python will map `pin_id` to `pin_name` and write `state_stats.csv.gz`.

## Objective-Term Gradient Norms

This is optional and should stay one-shot.

Instrumentation point: `dreamplace/PlaceObj.py`

Reason:

- that class already owns the wirelength term, density term, and optional pin-to-pin attraction term
- it can evaluate each contributed objective term with the same current position and current pair tensors

Plan:

- add a helper that computes a one-shot snapshot on demand
- use `torch.autograd.grad` to obtain raw gradient norms without disturbing the main optimization state
- only trigger it for the designated dump step and only when `dcf_diag_dump_term_grad_norms` is enabled

Expected output:

- `wirelength_term_value`
- `density_term_value`
- `pin2pin_term_value`
- `wirelength_grad_norm`
- `density_grad_norm`
- `pin2pin_grad_norm`

The file will be written as `objective_term_norms.json`.

## Same-State DCF vs Efficient-TDP Comparison

The existing `superblue16` config families are not placement-identical, so they cannot support a valid same-state first-step comparison by themselves.

To fix that without disturbing existing baselines:

- add a dedicated diagnostics config family
- for each case, create matched `pin2pin` and `dcf` configs with identical placement hyperparameters and deterministic settings
- only differ in timing-weighting fields and DCF enablement

The first timing step is the designated comparison point.

Why this works:

- both runs share the same placement state before the first timing update
- the `position_fingerprint` in `timing_steps.jsonl` gives a direct check that the two runs are being compared at the same placement state

## Output Layout

Diagnostics root:

- `results/diagnostics/<case>/<scheme>/`

Per scheme:

- `timing_steps.jsonl`
- `run_metadata.json`
- `config_used.json`
- `step_001/exported_pairs.csv.gz`
- `step_001/objective_term_norms.json` when enabled
- `step_001/state_stats.csv.gz` for DCF when enabled
- `step_001/utility_summary.json` for DCF

Per case:

- `results/diagnostics/<case>/compare_dcf_vs_pin2pin_step_001.json`

## Comparison Script

Create `scripts/compare_pair_dumps.py`.

Inputs:

- DCF `exported_pairs.csv.gz`
- Efficient-TDP `exported_pairs.csv.gz`

Outputs:

- total pair count by scheme
- overlap count
- top-K Jaccard overlap for K = 100, 1000, 5000
- weighted overlap summary
- rank correlation on shared pairs
- pair-length distribution stats for all pairs, top-100, and top-1000
- total weight mass
- top-K cumulative weight mass fraction

The script writes JSON so the comparison is machine-readable and easy to version.

## Minimal File Touch Set

- `dreamplace/params.json`
- `dreamplace/BasicPlace.py`
- `dreamplace/NonLinearPlace.py`
- `dreamplace/PlaceObj.py`
- `dreamplace/ops/timing/timing.py`
- `dreamplace/ops/timing/src/timing_cpp.h`
- `dreamplace/ops/timing/src/timing_cpp.cpp`
- `dreamplace/ops/timing/src/timing_pybind.cpp`
- `dreamplace/ops/timing/src/net_weighting_scheme.h`
- `test/CMakeLists.txt`
- new matched diagnostics configs under `test/`
- `scripts/compare_pair_dumps.py`

## Constraints Preserved

- no DCF tuning
- no change to DCF utility semantics
- no change to Efficient-TDP weighting semantics
- no change to DREAMPlace 4.0 semantics
- no redesign of the objective
- diagnostics remain optional and default-off
