# DCF Symmetric Replay Analysis

This note adds the symmetric same-state replay experiment for `superblue16` at timing step `10` using a snapshot saved from the `pin2pin` trajectory.

The replay setup was:

- save a replayable snapshot from the normal `pin2pin` run at step `10`
- replay that exact saved placement under `pin2pin`
- replay that exact saved placement under `dcf`
- compare the replayed pair rankings
- offline-rerank the replayed DCF dump with `original_dcf`, `no_eta`, `M_only`, and `S_only`

The saved snapshot metadata is:

- source scheme: `pin2pin`
- timing step: `10`
- GP iteration: `645`
- position fingerprint: `df0e6ca4b55ddc5b`

## New Outputs

- `results/diagnostics/superblue16/pin2pin/step_010/replay_snapshot/pos.pt`
- `results/diagnostics/superblue16/pin2pin/step_010/replay_snapshot/snapshot_metadata.json`
- `results/diagnostics/superblue16/pin2pin/step_010/replay_snapshot/config_used.json`
- `results/diagnostics/superblue16/pin2pin/step_010/replay_snapshot/position_fingerprint.txt`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/dcf/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/dcf/state_stats.csv.gz`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/dcf/state_stats_summary.json`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/dcf/utility_summary.json`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/dcf/histogram_activity_summary.json`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/dcf/timing_summary.json`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/pin2pin/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/replay_from_pin2pin_step_010/pin2pin/timing_summary.json`
- `results/diagnostics/superblue16/compare_replay_from_pin2pin_dcf_vs_pin2pin_step_010.json`
- `results/diagnostics/superblue16/offline_rerank_compare_replay_from_pin2pin_step_010.json`
- `results/diagnostics/superblue16/offline_rerank_topk_summary_replay_from_pin2pin_step_010.csv`

## Answers

### 1. On the fixed `pin2pin` step-10 state, how different are DCF and pin2pin rankings?

They are still different, but less different than on the DCF-sourced step-10 state.

Original replayed DCF vs replayed pin2pin top-K Jaccard:

- top-100: `0.28205`
- top-1000: `0.21359`
- top-5000: `0.30056`

Shared-pair statistics:

- overlap count: `31458`
- overlap fraction of union: `0.15110`
- weighted Jaccard: `0.20342`
- shared-pair weight Pearson correlation: `0.14042`
- shared-pair weight Spearman correlation: `0.53427`
- shared-pair rank Spearman correlation: `0.53342`

Top-1000 median length:

- replayed DCF: `1590.30`
- replayed pin2pin: `91.61`

So the same-state mismatch is still real, but the top-K overlap is materially better than on the DCF-sourced later state.

### 2. Does removing `eta` still account for most of the mismatch?

Yes.

Top-K Jaccard against replayed pin2pin:

- original DCF:
  - top-100: `0.28205`
  - top-1000: `0.21359`
  - top-5000: `0.30056`
- `no_eta`:
  - top-100: `0.94175`
  - top-1000: `0.94553`
  - top-5000: `0.73853`

Top-1000 median length:

- original DCF: `1590.30`
- `no_eta`: `90.90`
- replayed pin2pin: `91.61`

So on the `pin2pin`-sourced later state, removing `eta` again explains most of the ranking mismatch and almost all of the long-pair bias.

### 3. Is `M_only` still clearly closer to pin2pin than `S_only` on this state?

No.

On this state, `M_only`, `no_eta`, and `S_only` produce the same top-K overlaps and the same top-K length statistics:

- `M_only` vs pin2pin Jaccard:
  - top-100: `0.94175`
  - top-1000: `0.94553`
  - top-5000: `0.73853`
- `S_only` vs pin2pin Jaccard:
  - top-100: `0.94175`
  - top-1000: `0.94553`
  - top-5000: `0.73853`

Top-1000 median length:

- `M_only`: `90.90`
- `S_only`: `90.90`
- replayed pin2pin: `91.61`

The replayed DCF utility summary shows why:

- `T` is identically zero on this replayed state
- `M` and `S` have the same rank correlation with exported weights: Spearman `0.97856`

So on this fixed `pin2pin` state, `M_only` is not distinguishable from `S_only` by ranking quality.

### 4. Are higher bins active in top-ranked DCF pairs on this state?

No.

Replay DCF histogram activity on the `pin2pin` snapshot:

- global bin mass fractions:
  - `bin0`: `1.0`
  - `bin1`: `0.0`
  - `bin2`: `0.0`
  - `bin3`: `0.0`
- top-100 average bin composition:
  - `bin0`: `1.0`
  - `bin1`: `0.0`
  - `bin2`: `0.0`
  - `bin3`: `0.0`
- top-1000 average bin composition:
  - `bin0`: `1.0`
  - `bin1`: `0.0`
  - `bin2`: `0.0`
  - `bin3`: `0.0`
- positive-`T` fraction overall: `0.0`
- positive-`T` fraction in top-100: `0.0`
- positive-`T` fraction in top-1000: `0.0`

So the higher-bin activation seen on the DCF-sourced later state does not appear on the `pin2pin`-sourced later state.

### 5. Do the DCF-sourced replay conclusions survive on the pin2pin-sourced replay?

Only partly.

What survives:

- `eta` is still the dominant source of ranking mismatch
- removing `eta` still moves the replayed DCF ranking very close to replayed `pin2pin`

What does not survive on this source state:

- higher-bin activity in top DCF pairs
- a clear `M_only` vs `S_only` separation

Direct comparison of top-1000 Jaccard vs replayed pin2pin:

- DCF-sourced snapshot:
  - original DCF: `0.14090`
  - `no_eta`: `0.58228`
  - `M_only`: `0.82315`
  - `S_only`: `0.58228`
- pin2pin-sourced snapshot:
  - original DCF: `0.21359`
  - `no_eta`: `0.94553`
  - `M_only`: `0.94553`
  - `S_only`: `0.94553`

So the stronger claim about `M` being clearly better aligned than `S` is not trajectory-robust across both later states by itself. It appears only on the later state where higher bins are actually active.

### 6. What does the combined evidence support now?

The combined evidence supports a conditional interpretation:

- early failure: mostly `eta`
- later failure on both tested source states: still strongly `eta`-dominated
- when higher bins are not active, `M_only` and `S_only` collapse to the same ranking on the fixed state
- when higher bins are active, `M_only` is more aligned with pin2pin than `S_only`

This is consistent with:

- the DCF-sourced later state representing a regime where higher-bin utility is active and matters
- the pin2pin-sourced later state representing a regime where `T=0` and the higher-bin distinction is inactive

## Length Bias Summary

Top-1000 median lengths on the `pin2pin` snapshot:

- replayed pin2pin: `91.61`
- original DCF: `1590.30`
- `no_eta`: `90.90`
- `M_only`: `90.90`
- `S_only`: `90.90`

So the long-pair bias is almost entirely removed once `eta` is removed on this source state.

## Additional Observation

The replayed DCF state stats on the `pin2pin` snapshot are still very sharp:

- mass-weighted `max_prob` mean: `0.99057`
- mass-weighted `top3_prob_sum` mean: `0.99096`
- mass-weighted normalized entropy mean: `0.00414`

So this replay also does not support a broadly diffuse reverse-attribution explanation.

## Caveats

- This replay used fresh-state semantics rather than restoring prior accumulated weights.
- TNS and WNS are identical across replayed schemes because both replays analyze the same fixed placement state.
- The pin2pin replay and DCF replay should be run serially against the shared `install/` runtime root; parallel replay caused one transient STA initialization failure during this work.
