# DCF Same-State Replay Analysis

This note adds a same-state replay experiment for `superblue16` at timing step `10`.

Unlike the earlier step-2 and step-10 comparisons, this experiment holds the placement state fixed:

- a replayable snapshot was saved from the normal `dcf` run at `superblue16` step `10`
- that exact saved placement was replayed under both `dcf` and `pin2pin`
- the replay used a fresh weighting state rather than restoring prior accumulated weights

The saved snapshot metadata is:

- source scheme: `dcf`
- timing step: `10`
- GP iteration: `645`
- position fingerprint: `d0e8c97d9158e756`

## What Changed

- selected timing steps can now save replayable placement snapshots
- a standalone replay script can reconstruct timing and weight generation from a saved snapshot without continuing optimization

## New Script

- `scripts/replay_timing_weights.py`

## New Outputs

- `results/diagnostics/superblue16/dcf/step_010/replay_snapshot/pos.pt`
- `results/diagnostics/superblue16/dcf/step_010/replay_snapshot/snapshot_metadata.json`
- `results/diagnostics/superblue16/dcf/step_010/replay_snapshot/config_used.json`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/dcf/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/dcf/state_stats.csv.gz`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/dcf/state_stats_summary.json`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/dcf/utility_summary.json`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/dcf/histogram_activity_summary.json`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/dcf/timing_summary.json`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/pin2pin/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/replay_from_dcf_step_010/pin2pin/timing_summary.json`
- `results/diagnostics/superblue16/compare_replay_dcf_vs_pin2pin_step_010.json`
- `results/diagnostics/superblue16/offline_rerank_compare_replay_step_010.json`
- `results/diagnostics/superblue16/offline_rerank_topk_summary_replay_step_010.csv`

## Answers

### 1. On the exact same `superblue16` step-10 placement state, how different are DCF and pin2pin rankings?

They are still meaningfully different even when the placement state is fixed.

Same-state replay top-K Jaccard:

- top-100: `0.08696`
- top-1000: `0.14090`
- top-5000: `0.22684`

Shared-pair statistics:

- overlap count: `128348`
- overlap fraction of union: `0.23013`
- weighted Jaccard: `0.28843`
- shared-pair weight Pearson correlation: `0.09152`
- shared-pair weight Spearman correlation: `0.55204`
- shared-pair rank Spearman correlation: `0.55281`

Length bias remains large in the top DCF ranks:

- DCF top-1000 median length: `10014.15`
- pin2pin top-1000 median length: `182.95`

So the same-state mismatch is still strong at step 10.

### 2. On that same state, does removing `eta` still account for most of the mismatch?

Yes.

Top-K Jaccard against same-state `pin2pin`:

- original DCF:
  - top-100: `0.08696`
  - top-1000: `0.14090`
  - top-5000: `0.22684`
- `no_eta`:
  - top-100: `0.53846`
  - top-1000: `0.58228`
  - top-5000: `0.78158`

Top-K length change:

- top-1000 median length
  - original DCF: `10014.15`
  - `no_eta`: `613.05`

So removing `eta` still explains a large share of the same-state ranking mismatch and long-pair bias.

### 3. On that same state, do `M_only` and `S_only` diverge meaningfully?

Yes.

Top-K Jaccard against same-state `pin2pin`:

- `M_only`:
  - top-100: `0.73913`
  - top-1000: `0.82315`
  - top-5000: `0.82017`
- `S_only`:
  - top-100: `0.53846`
  - top-1000: `0.58228`
  - top-5000: `0.78158`

Top-1000 median length:

- `M_only`: `373.66`
- `S_only`: `613.05`

So `M_only` and `S_only` do diverge meaningfully on the fixed step-10 state.

### 4. If they diverge, which one is closer to pin2pin?

`M_only` is closer to pin2pin.

- top-1000 Jaccard: `M_only 0.82315` vs `S_only 0.58228`
- top-100 Jaccard: `M_only 0.73913` vs `S_only 0.53846`
- top-1000 median length: `M_only 373.66` vs `S_only 613.05`

So on this same later state, `M` is more aligned with pin2pin than `S` alone.

### 5. On that same state, are higher histogram bins truly active in the top-ranked DCF pairs?

Yes.

Global replay histogram mass fractions:

- `bin0`: `0.96284`
- `bin1`: `0.03399`
- `bin2`: `0.00317`
- `bin3`: `0.0`

Top-rank average bin composition:

- top-100:
  - `bin0`: `0.45820`
  - `bin1`: `0.45660`
  - `bin2`: `0.08519`
- top-1000:
  - `bin0`: `0.71125`
  - `bin1`: `0.27030`
  - `bin2`: `0.01845`

`T` activity:

- overall positive-`T` fraction: `0.00032`
- top-100 positive-`T` fraction: `0.19`
- top-1000 positive-`T` fraction: `0.062`

So higher bins are clearly active in the top replayed DCF pairs even though global mass is still mostly in bin 0.

### 6. Does the same-state replay support the interpretation that early failure is mostly `eta`, while later failure is still `eta` dominated but now also influenced by the distributional utility?

Yes, with the fresh-state replay caveat.

What the same-state replay shows:

- removing `eta` still gives the biggest single improvement over original DCF
- but `M_only` is now substantially closer to pin2pin than `S_only`
- and higher histogram bins are genuinely active in the top-ranked DCF pairs on this fixed later state

Useful same-state numbers:

- original DCF top-1000 Jaccard vs pin2pin: `0.14090`
- `no_eta` top-1000 Jaccard vs pin2pin: `0.58228`
- `M_only` top-1000 Jaccard vs pin2pin: `0.82315`
- `S_only` top-1000 Jaccard vs pin2pin: `0.58228`

This supports the interpretation:

- early failure: mostly `eta`
- later step-10 failure on the same state: still strongly `eta`-dominated, but the distributional utility is no longer inert

## Additional Observation

The replayed DCF state stats are still fairly sharp on high-mass states:

- mass-weighted `max_prob` mean: `0.97787`
- mass-weighted `top3_prob_sum` mean: `0.97887`
- mass-weighted normalized entropy mean: `0.01128`

So the same-state later-step mismatch still does not look well explained by broadly diffuse reverse attribution.

## Caveats

- This replay used a fresh weighting state rather than restoring prior accumulated weights, so it isolates same-state scheme preference rather than exact online step-10 history.
- TNS and WNS are identical across replayed schemes because both replays analyze the same fixed placement state.
- This note answers the same-state ranking question only; it does not show how these replayed rankings would feed back into later placement if used online.
