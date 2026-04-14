# DCF v3c Beta Sweep

This note records the narrow beta sweep follow-up on branch `exp/dcf-v3`.

## What Changed

- Added explicit `v3c` beta configs for `superblue16` and `superblue18`:
  - `b005`, `b010`, `b015`, `b020`, `b025`
- Extended `scripts/run_dcf_v3_experiments.sh` so it can:
  - run the `v1` / `v3b` / `v3c` sweep matrix
  - select methods by key
  - write to isolated output roots for repeat runs
- Extended `scripts/collect_experiment_metrics.py` to record:
  - `method_key`
  - `variant`
  - `beta`
  - `output_tag`
  - `run_label`
- Added `scripts/summarize_dcf_v3_beta_sweep.py` to build local summary CSVs from the lightweight timing-step outputs

No propagation logic changed.
No bin structure changed.
No objective or baseline path changed.

## Sweep Definition

The swept utility was unchanged except for `beta`:

- `v3c`: `U = M + beta * T`
- final export: `w = log(1 + U)`

Swept values:

- `beta = 0.05`
- `beta = 0.10`
- `beta = 0.15`
- `beta = 0.20`
- `beta = 0.25`

Comparison methods in this pass:

- `DCF v1`
- `DCF v3b`
- `DCF v3c` at each beta above

## What Was Run

- Sweep cases:
  - `superblue18`
  - `superblue16`
- Stability reruns on `superblue16`:
  - `DCF v1`
  - `DCF v3b`
  - `DCF v3c beta=0.25`

Local summary artifacts were generated at:

- `results/dcf_v3_beta_sweep/summary/beta_sweep_metrics.csv`
- `results/dcf_v3_beta_sweep/summary/superblue16_stability.csv`
- `results/dcf_v3_beta_sweep/summary/superblue16_trajectory_long.csv`
- `results/dcf_v3_beta_sweep/summary/superblue16_trajectory_vs_v3b.csv`

## Beta Sweep Results

### superblue18

| method | beta | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- |
| DCF v1 | - | -17.798613 | -7.231050 | 2.373351E+08 | 226.519 |
| DCF v3b | - | -17.262021 | -7.101406 | 2.332934E+08 | 241.373 |
| DCF v3c | 0.05 | -17.605326 | -7.038018 | 2.333063E+08 | 237.880 |
| DCF v3c | 0.10 | -17.358376 | -6.951991 | 2.328330E+08 | 274.524 |
| DCF v3c | 0.15 | -17.526309 | -7.109611 | 2.332873E+08 | 243.099 |
| DCF v3c | 0.20 | -17.387040 | -7.078022 | 2.333748E+08 | 233.051 |
| DCF v3c | 0.25 | -17.377916 | -7.102151 | 2.332968E+08 | 233.399 |

### superblue16

| method | beta | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- |
| DCF v1 | - | -99.117940 | -17.925586 | 4.905974E+08 | 224.523 |
| DCF v3b | - | -69.504020 | -22.065291 | 4.397976E+08 | 227.361 |
| DCF v3c | 0.05 | -66.840255 | -22.649115 | 4.398793E+08 | 224.896 |
| DCF v3c | 0.10 | -123.004270 | -18.626750 | 4.391808E+08 | 223.286 |
| DCF v3c | 0.15 | -84.143690 | -16.959045 | 4.398238E+08 | 235.010 |
| DCF v3c | 0.20 | -51.622550 | -16.423551 | 4.390207E+08 | 222.710 |
| DCF v3c | 0.25 | -61.251220 | -21.320693 | 4.397108E+08 | 223.668 |

## Stability Check: superblue16

This table compares the fresh sweep run against one additional repeat run.

| method | beta | previous TNS | repeat TNS | previous WNS | repeat WNS | previous HPWL | repeat HPWL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DCF v1 | - | -99.117940 | -74.930640 | -17.925586 | -16.626910 | 4.905974E+08 | 4.903485E+08 |
| DCF v3b | - | -69.504020 | -73.461280 | -22.065291 | -35.759039 | 4.397976E+08 | 4.394699E+08 |
| DCF v3c | 0.25 | -61.251220 | -112.477060 | -21.320693 | -17.509695 | 4.397108E+08 | 4.384692E+08 |

Observed deltas:

- `v1` repeat improved timing slightly and reduced HPWL slightly.
- `v3b` repeat kept similar TNS / HPWL, but WNS degraded sharply.
- `v3c beta=0.25` repeat improved HPWL and WNS, but TNS degraded sharply.

So the `superblue16` ordering between `v3b` and `v3c beta=0.25` is not stable enough yet to call settled from this one repeat.

## Trajectory Summary: superblue16

The full local trajectory files are:

- `results/dcf_v3_beta_sweep/summary/superblue16_trajectory_long.csv`
- `results/dcf_v3_beta_sweep/summary/superblue16_trajectory_vs_v3b.csv`

Main observations from the timing-step trajectories:

- All `v3c` betas are effectively identical to `v3b` at timing step `1`.
- Through roughly timing steps `2` to `6`, the `v3c` trajectories remain very close to `v3b` in both WNS and exported weight mass.
- The first noticeable WNS separation from `v3b` appears around timing step `7`, but it is still modest.
- The largest negative WNS deltas versus `v3b` occur late, at timing step `12`, for every swept beta.
- The larger-beta runs mainly change late-stage behavior rather than the early steps.
- Exported pair count and total exported weight mass also separate more clearly in the later timing steps than in the first half of the run.

Examples from `superblue16_trajectory_vs_v3b.csv`:

- `beta=0.20` vs `v3b`
  - step `7`: `wns_delta_vs_v3b = -0.3969`
  - step `12`: `wns_delta_vs_v3b = -12.4282`
- `beta=0.25` vs `v3b`
  - step `7`: `wns_delta_vs_v3b = -0.3891`
  - step `12`: `wns_delta_vs_v3b = -12.1859`

So the data supports a late-stage divergence story more than an early-stage one.

## Answers

### 1. Does smaller `beta` improve WNS relative to `beta=0.25`?

Yes, but not monotonically.

- On `superblue18`, `beta=0.10` gives the best WNS (`-6.951991`) and improves on `0.25` (`-7.102151`).
- On `superblue16`, `beta=0.10`, `0.15`, and `0.20` all improve WNS relative to `0.25`.
- `beta=0.05` does not improve WNS on `superblue16` relative to `0.25`.

### 2. Which `beta` gives the best balance of TNS / WNS / HPWL?

Per case:

- `superblue18`: `beta=0.10`
  - best WNS and best HPWL in the sweep
  - TNS is slightly worse than `v3b`, but still competitive
- `superblue16`: `beta=0.20`
  - best TNS, best WNS, and best HPWL in the sweep

Across both cases, the single best near-term candidate from this pass is `v3c beta=0.20`.

### 3. Is `v3c` clearly better than `v3b` on `superblue16` once stability is checked?

Not clearly, yet.

- In the sweep run, `v3c beta=0.20` is clearly better than `v3b` on all three top-line metrics.
- But the requested repeat was only run for `v3c beta=0.25`, not `0.20`.
- For `beta=0.25`, the repeat changed the ordering materially: the repeat improved WNS and HPWL, but TNS became much worse.

So the `v3c` family looks promising on `superblue16`, but the stability check says we should not over-claim yet.

### 4. At what stage does larger `beta` start to hurt WNS?

It does not show a strong early monotonic penalty.

- Differences from `v3b` are tiny through the first several timing steps.
- Noticeable WNS separation shows up around timing step `7`.
- The strongest WNS degradation relative to `v3b` appears late, around timing step `12`.

So the effect looks mostly late-stage, not early-stage.

### 5. Based on the current data, what is the single best next candidate configuration?

- `DCF v3c` with `beta = 0.20`

Reason:

- it is the best point on the key problem case `superblue16`
- it remains competitive on `superblue18`
- it improves on the current `beta=0.25` setting on both cases in this sweep

## Conservative Takeaway

- `beta=0.25` does look too aggressive relative to the sweep results.
- A smaller tail term helps, and the best point in this pass is not the smallest beta.
- `beta=0.20` is the strongest immediate follow-up candidate.
- Before calling it the new default v3c point, it should get the same repeat check that was just applied to `beta=0.25`.
