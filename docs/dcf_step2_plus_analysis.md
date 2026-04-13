# DCF Step-2 Plus Analysis

This note extends the existing diagnostics from step 1 to later `superblue16` timing steps using the same diagnostics framework.

## What Changed

- detailed dump selection was generalized from step 1 only to arbitrary timing step ids
- a new offline script summarizes DCF histogram activity from dumped pair histograms

## New Scripts

- `scripts/summarize_dcf_histogram_activity.py`

## New Inputs Produced

Matched `superblue16` runs were executed for:

- `pin2pin` with detailed dumps at steps `2` and `10`
- `dcf` with detailed dumps at steps `2` and `10`

Step `10` was chosen as the later problematic step because:

- it is one of the preferred candidate steps
- it is reached by both matched runs without changing placement stop behavior
- by step `10`, DCF timing is already clearly poor relative to `pin2pin`

At step `10`:

- `dcf`: `TNS -377.4940`, `WNS -80.5596`
- `pin2pin`: `TNS -28.1349`, `WNS -11.1975`

## New Outputs

- `results/diagnostics/superblue16/pin2pin/step_002/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/pin2pin/step_002/objective_term_norms.json`
- `results/diagnostics/superblue16/pin2pin/step_010/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/pin2pin/step_010/objective_term_norms.json`
- `results/diagnostics/superblue16/dcf/step_002/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/dcf/step_002/state_stats.csv.gz`
- `results/diagnostics/superblue16/dcf/step_002/state_stats_summary.json`
- `results/diagnostics/superblue16/dcf/step_002/utility_summary.json`
- `results/diagnostics/superblue16/dcf/step_002/histogram_activity_summary.json`
- `results/diagnostics/superblue16/dcf/step_002/objective_term_norms.json`
- `results/diagnostics/superblue16/dcf/step_010/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/dcf/step_010/state_stats.csv.gz`
- `results/diagnostics/superblue16/dcf/step_010/state_stats_summary.json`
- `results/diagnostics/superblue16/dcf/step_010/utility_summary.json`
- `results/diagnostics/superblue16/dcf/step_010/histogram_activity_summary.json`
- `results/diagnostics/superblue16/dcf/step_010/objective_term_norms.json`
- `results/diagnostics/superblue16/compare_dcf_vs_pin2pin_step_002.json`
- `results/diagnostics/superblue16/compare_dcf_vs_pin2pin_step_010.json`
- `results/diagnostics/superblue16/offline_rerank_compare_step_002.json`
- `results/diagnostics/superblue16/offline_rerank_compare_step_010.json`

## Answers

### 1. On `superblue16` step 2, is DCF still sharply attributed on high-mass states?

Yes.

Mass-weighted step-2 attribution statistics:

- `max_prob` mean: `0.98268`
- `top3_prob_sum` mean: `0.98315`
- `attribution_entropy` mean: `0.00126`
- normalized entropy mean: `0.00764`
- mass-weighted fraction `max_prob >= 0.9`: `0.98188`
- mass-weighted fraction `num_candidate_predecessors == 1`: `0.82733`
- mass-weighted fraction `num_candidate_predecessors >= 3`: `0.04151`

So step 2 is still sharply attributed on large-mass states.

### 2. On step 2, does removing `eta` still make DCF much closer to `pin2pin`?

Only modestly.

Step-2 top-K Jaccard against `pin2pin`:

- original DCF:
  - top-100: `0.15607`
  - top-1000: `0.12423`
  - top-5000: `0.07724`
- `no_eta`:
  - top-100: `0.18343`
  - top-1000: `0.16482`
  - top-5000: `0.36073`

Length bias also drops strongly:

- top-1000 median length
  - original DCF: `3353.96`
  - `no_eta`: `196.12`

So by step 2, removing `eta` still helps materially, especially at top-5000 and in pair-length bias, but it no longer restores near-pin2pin agreement the way it did at step 1.

### 3. On step 2, are higher histogram bins active, or is DCF still effectively single-bin?

Step 2 is still effectively a low-bin regime.

Step-2 histogram activity:

- total histogram mass fraction:
  - `bin0`: `0.99046`
  - `bin1`: `0.00954`
  - `bin2`: `0.0`
  - `bin3`: `0.0`
- pair fraction with nonzero contribution:
  - `bin1`: `0.00309`
  - `bin2`: `0.0`
  - `bin3`: `0.0`
- `T` summary:
  - mean: `0.0`
  - fraction positive: `0.0`

So step 2 is not yet meaningfully distributional in the higher-bin sense.

### 4. On the later selected step, are higher bins materially active?

Yes, at step 10 they are active in the high-ranked DCF pairs, although not yet dominant globally.

Step-10 histogram activity:

- total histogram mass fraction:
  - `bin0`: `0.95463`
  - `bin1`: `0.03995`
  - `bin2`: `0.00542`
  - `bin3`: `0.0`
- pair fraction with nonzero contribution:
  - `bin1`: `0.01093`
  - `bin2`: `0.00117`
  - `bin3`: `0.0`

Top-rank composition shows stronger activation than the global totals:

- top-100 average bin composition:
  - `bin0`: `0.13053`
  - `bin1`: `0.74235`
  - `bin2`: `0.12712`
- top-1000 average bin composition:
  - `bin0`: `0.72188`
  - `bin1`: `0.25999`
  - `bin2`: `0.01814`

`T` is no longer identically zero:

- overall `T` mean: `18.78`
- overall positive-`T` fraction: `0.00117`
- positive-`T` fraction in top-100: `0.22`
- positive-`T` fraction in top-1000: `0.056`

So higher bins are materially active by step 10 in the top DCF-ranked pairs.

### 5. On the later selected step, is `eta` still the dominant mismatch source, or do `M_only` / `S_only` begin to diverge in meaningful ways?

`eta` still appears to be the dominant mismatch source, but `M_only` and `S_only` no longer behave identically.

Step-10 top-K Jaccard against `pin2pin`:

- original DCF:
  - top-1000: `0.03842`
  - top-5000: `0.04439`
- `no_eta`:
  - top-1000: `0.08401`
  - top-5000: `0.19432`
- `S_only`:
  - top-1000: `0.08401`
  - top-5000: `0.19432`
- `M_only`:
  - top-1000: `0.09951`
  - top-5000: `0.20207`

Step-10 top-1000 median length:

- original DCF: `14714.61`
- `no_eta`: `1059.52`
- `S_only`: `1059.52`
- `M_only`: `566.08`

This indicates:

- removing `eta` still produces the largest single improvement over original DCF
- by step 10, `M_only` is measurably better than `S_only` and `no_eta`
- `S_only` remains aligned with `no_eta`, while `M_only` starts to separate

So some meaningful divergence inside the distributional utility has started to appear by step 10.

### 6. Does the evidence suggest that the next problem to debug is still length bias, or has the distributional utility itself started to become problematic?

The data suggests:

- step 2: still mainly a length-bias problem
- step 10: still primarily length-bias-dominated, but now with early evidence that the distributional utility itself is beginning to matter

Why:

- step 10 raw DCF vs pin2pin mismatch is extreme
- removing `eta` improves top-5000 Jaccard from `0.04439` to `0.19432`
- removing `eta` cuts top-1000 median length from `14714.61` to `1059.52`
- but `M_only` then improves further to `0.20207` at top-5000 and shortens top-1000 median length to `566.08`

So the next debugging target still looks like length bias first, but step 10 shows that the true distributional utility is no longer completely inert once higher bins begin to activate.

## What Remains Unknown

- These are not same-placement-state comparisons like step 1; by steps 2 and 10 the two runs have already diverged.
- The offline reranking analysis does not show how these alternative rankings would feed back into placement if actually used online.
- Step 10 is the latest preferred candidate reached by both matched runs without altering termination; this report does not yet cover even later DCF-only regimes such as steps 20 or 24.
