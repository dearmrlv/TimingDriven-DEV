# DCF v3 Superblue16 Beta 0.15 And 0.20 Repeat Check

This note isolates the narrow question of whether `DCF v3c beta=0.20` is stable enough to promote as the best current candidate on `superblue16`, using `beta=0.15` as the immediate nearby control.

No algorithm changes were made.
No propagation, histogram, or objective changes were made.
No new diagnostics machinery was added.

## Tracked Artifacts

- `docs/artifacts/dcf_v3_superblue16_beta015_020_repeat_metrics.csv`
- `docs/artifacts/dcf_v3_superblue16_beta015_020_repeat_stability.csv`
- `docs/artifacts/dcf_v3_superblue16_beta015_020_repeat_trajectory.csv`

`v3b` is included in the metrics table as the existing reference point for deciding whether either `v3c` variant still looks better overall. It is not included in the narrow stability CSV because the requested repeat focus here is `beta=0.15` vs `beta=0.20`.

## Summary Table

| method | beta | run_tag | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- |
| DCF v3b | - | sweep | -69.504020 | -22.065291 | 4.397976E+08 | 227.361 |
| DCF v3c | 0.15 | sweep | -84.143690 | -16.959045 | 4.398238E+08 | 235.010 |
| DCF v3c | 0.20 | sweep | -51.622550 | -16.423551 | 4.390207E+08 | 222.710 |
| DCF v3b | - | repeat1 | -66.987350 | -18.796805 | 4.393643E+08 | 267.778 |
| DCF v3c | 0.15 | repeat1 | -117.033870 | -28.539422 | 4.389099E+08 | 254.184 |
| DCF v3c | 0.20 | repeat1 | -132.324990 | -25.086047 | 4.393574E+08 | 243.486 |

## Stability Table

| method | beta | delta TNS | delta WNS | delta HPWL | delta runtime (s) |
| --- | --- | --- | --- | --- | --- |
| DCF v3c | 0.15 | -32.890180 | -11.580377 | -913900.000000 | 19.174000 |
| DCF v3c | 0.20 | -80.702440 | -8.662496 | 336700.000000 | 20.776000 |

Interpretation:

- Positive `delta TNS` / `delta WNS` would mean the repeat improved because the numbers became less negative.
- Negative `delta HPWL` means the repeat improved HPWL.

## Trajectory Takeaways

The compact repeat trajectory file is:

- `docs/artifacts/dcf_v3_superblue16_beta015_020_repeat_trajectory.csv`

Main observations:

- `beta=0.15` and `beta=0.20` are nearly identical through the early timing steps.
- The larger differences appear late rather than early.
- At timing step `12`, both variants are worse than repeat `v3b` on WNS:
  - `beta=0.15`: `wns_delta_vs_v3b_repeat = -0.154348`
  - `beta=0.20`: `wns_delta_vs_v3b_repeat = -0.341072`
- At the same step, both variants also show clear TNS damage versus repeat `v3b`:
  - `beta=0.15`: `tns_delta_vs_v3b_repeat = -26.378770`
  - `beta=0.20`: `tns_delta_vs_v3b_repeat = -13.833580`
- `beta=0.15` runs one more timing step and ends poorly (`TNS -116.94091`, `WNS -28.533640625`).

So the repeat trajectory does not support calling `beta=0.20` especially well-behaved. The instability still looks predominantly late-stage.

## Answers

### 1. Is `beta=0.20` still better than `beta=0.15` after a repeat run on `superblue16`?

Not clearly.

- On the repeat run, `beta=0.20` is better than `beta=0.15` on WNS (`-25.086047` vs `-28.539422`).
- But it is worse on TNS (`-132.324990` vs `-117.033870`) and worse on HPWL (`4.393574E+08` vs `4.389099E+08`).

So the repeat result does not preserve a clear overall advantage for `beta=0.20` over `beta=0.15`.

### 2. Is `beta=0.20` still a better overall TNS/WNS/HPWL tradeoff than the existing `v3b` reference?

No.

- Repeat `v3b` beats repeat `beta=0.20` on both TNS and WNS.
- Repeat `v3b` also has slightly better HPWL than repeat `beta=0.20`.

So `beta=0.20` is not the better overall tradeoff after the repeat.

### 3. Are the differences between `beta=0.15` and `beta=0.20` stable enough to justify promoting one of them as the best current candidate?

No.

- Both variants regressed sharply relative to their sweep runs.
- The repeat changed the metric ordering enough that neither one looks stable enough to promote.

### 4. Do the timing-step trajectories suggest that `beta=0.20` remains well-behaved, or does it show unstable late-stage behavior relative to `beta=0.15`?

It shows unstable late-stage behavior, not a clearly well-behaved improvement.

- Early steps remain close.
- The meaningful separation appears late.
- By the later timing steps, both variants are clearly worse than repeat `v3b`, and `beta=0.20` does not show a convincingly safer pattern than `beta=0.15`.

### 5. Based on the repeat check, should we promote `beta=0.20`, prefer `beta=0.15`, or defer?

- Defer.

More specifically:

- do not promote `beta=0.20`
- do not switch to `beta=0.15` as the safer choice
- keep the method direction as `v3`, but avoid entering the next version yet based on these `superblue16` repeats alone

## Recommendation

### Is `beta=0.20` stable enough to promote as the best current candidate?

No.

### Is `beta=0.15` a safer alternative?

No, not from the current evidence.

### Does the current evidence support formally moving on to the next version, or should we stay on v3 and do one more narrow check?

Stay on `v3` and do one more narrow check rather than promoting a new best point from this pair.

### What is the single recommended next action?

- Do not promote either `v3c beta=0.15` or `v3c beta=0.20` yet.
- Keep `v3b` as the more defensible reference point on `superblue16` until a narrower, more stable confirmation is available.
