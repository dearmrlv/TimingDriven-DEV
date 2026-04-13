# DCF Offline Analysis

This note summarizes two offline analyses over the existing diagnostics dumps under `results/diagnostics/`.

## Scripts Added

- `scripts/summarize_dcf_state_stats.py`
- `scripts/offline_rerank_dcf_pairs.py`

## Existing Inputs Analyzed

- `results/diagnostics/superblue18/dcf/step_001/state_stats.csv.gz`
- `results/diagnostics/superblue16/dcf/step_001/state_stats.csv.gz`
- `results/diagnostics/superblue18/dcf/step_001/exported_pairs.csv.gz`
- `results/diagnostics/superblue18/pin2pin/step_001/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/dcf/step_001/exported_pairs.csv.gz`
- `results/diagnostics/superblue16/pin2pin/step_001/exported_pairs.csv.gz`
- existing `compare_dcf_vs_pin2pin_step_001.json`
- existing `timing_steps.jsonl`
- existing `utility_summary.json`

## Outputs Generated

- `results/diagnostics/superblue18/dcf/step_001/state_stats_summary.json`
- `results/diagnostics/superblue16/dcf/step_001/state_stats_summary.json`
- `results/diagnostics/superblue18/offline_rerank_compare_step_001.json`
- `results/diagnostics/superblue16/offline_rerank_compare_step_001.json`
- `results/diagnostics/superblue18/offline_rerank_topk_summary.csv`
- `results/diagnostics/superblue16/offline_rerank_topk_summary.csv`

## Main Findings

### 1. On `superblue16`, is attribution actually diffuse?

The first-step DCF attribution does not look broadly diffuse, especially after weighting by state mass.

- `superblue16` mass-weighted sharpness:
  - `max_prob` mean: `0.9869`
  - `top3_prob_sum` mean: `0.9876`
  - `attribution_entropy` mean: `0.00146`
  - normalized entropy mean: `0.00910`
- `superblue16` mass-weighted fractions:
  - `max_prob >= 0.9`: `0.9859`
  - `max_prob <= 0.3`: `0.01235`
  - `num_candidate_predecessors == 1`: `0.8379`
  - `num_candidate_predecessors >= 3`: `0.0317`
  - `top3_prob_sum >= 0.95`: `0.9876`

This indicates that high-mass states are usually assigned to one predecessor or a very small predecessor set with high confidence.

### 2. Does removing `eta` make DCF much closer to `pin2pin`?

Yes, strongly, on both cases.

- `superblue16`
  - original DCF vs pin2pin Jaccard:
    - top-1000: `0.1710`
    - top-5000: `0.1478`
  - `no_eta` vs pin2pin Jaccard:
    - top-1000: `0.9436`
    - top-5000: `0.9309`
  - top-1000 median length:
    - original DCF: `7279.53`
    - `no_eta`: `172.45`
- `superblue18`
  - original DCF vs pin2pin Jaccard:
    - top-1000: `0.3652`
    - top-5000: `0.5349`
  - `no_eta` vs pin2pin Jaccard:
    - top-1000: `0.9881`
    - top-5000: `0.8406`
  - top-1000 median length:
    - original DCF: `596.03`
    - `no_eta`: `72.89`

### 3. Between `M_only` and `S_only`, which is closer to `pin2pin` and which reduces long-pair bias more?

In these first-step dumps, `M_only` and `S_only` produce the same ranking behavior as `no_eta` for top-K overlap and top-K length statistics on both cases.

- `superblue16`
  - `M_only` vs pin2pin Jaccard:
    - top-1000: `0.9436`
    - top-5000: `0.9309`
  - `S_only` vs pin2pin Jaccard:
    - top-1000: `0.9436`
    - top-5000: `0.9309`
  - both reduce top-1000 median length from `7279.53` to `172.45`
- `superblue18`
  - `M_only` vs pin2pin Jaccard:
    - top-1000: `0.9881`
    - top-5000: `0.8406`
  - `S_only` vs pin2pin Jaccard:
    - top-1000: `0.9881`
    - top-5000: `0.8406`
  - both reduce top-1000 median length from `596.03` to `72.89`

So, from the current offline ranking data alone, neither `M_only` nor `S_only` is closer than the other; they tie.

### 4. Is original DCF more concentrated or less concentrated than the offline variants?

Original DCF is less concentrated than the offline variants.

- `superblue16` top-1000 score fraction:
  - original DCF: `0.01458`
  - `no_eta`: `0.01513`
  - `S_only`: `0.01513`
  - `M_only`: `0.01988`
- `superblue18` top-1000 score fraction:
  - original DCF: `0.04976`
  - `no_eta`: `0.05276`
  - `S_only`: `0.05276`
  - `M_only`: `0.07005`

This means the existing DCF ranking is broader and less top-heavy than the offline variants that remove `eta` or isolate `M`/`S`.

### 5. Does the evidence support `eta` as a major source of ranking mismatch?

Yes, the offline evidence supports that hypothesis.

- attribution sharpness on `superblue16` is already high on large-mass states, so the mismatch is not well explained by a broadly diffuse reverse pass at the first timing step
- removing `eta` changes top-K overlap with pin2pin from poor to very high on both cases
- removing `eta` also removes most of the very long-pair bias in the DCF top ranks

The strongest numeric evidence is on `superblue16`, where top-1000 Jaccard improves from `0.1710` to `0.9436`, and top-1000 median length drops from `7279.53` to `172.45`.

## What Remains Unknown

- This is a first-step offline analysis only. It does not prove how these alternative rankings would behave if they were fed back into placement over multiple timing updates.
- The rerank analysis changes ranking only; it does not evaluate downstream objective coupling or placement response.
- `M_only`, `S_only`, and `no_eta` are highly aligned in these dumps, but the current data does not explain whether that alignment is specific to step 1 or to these two cases.
