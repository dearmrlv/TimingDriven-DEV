# DCF v3 Superblue16 Stability Check

This note records the minimal repeat check requested on `superblue16` for the current near-term candidates:

- `DCF v3b`
- `DCF v3c beta=0.15`
- `DCF v3c beta=0.20`

No algorithm changes were made.
No propagation, histogram, or objective changes were made.
No new diagnostics framework was added.

## Tracked Artifacts

- `docs/artifacts/dcf_v3_superblue16_repeat_metrics.csv`
- `docs/artifacts/dcf_v3_superblue16_repeat_stability.csv`
- `docs/artifacts/dcf_v3_superblue16_repeat_trajectory.csv`

These are the reviewable small artifacts for this follow-up run.

## Run Summary

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
| DCF v3b | - | 2.516670 | 3.268486 | -433300.000000 | 40.417000 |
| DCF v3c | 0.15 | -32.890180 | -11.580377 | -913900.000000 | 19.174000 |
| DCF v3c | 0.20 | -80.702440 | -8.662496 | 336700.000000 | 20.776000 |

Interpretation of the deltas:

- Positive `delta TNS` / `delta WNS` means the repeat improved because the numbers became less negative.
- Negative `delta HPWL` means the repeat improved HPWL.

## Trajectory Summary

The repeat trajectory file contains per-step values and deltas versus the repeat `v3b` run:

- `docs/artifacts/dcf_v3_superblue16_repeat_trajectory.csv`

Main observations:

- All three methods are effectively identical at timing step `1`.
- Through timing steps `2` to `9`, `v3c beta=0.15` and `v3c beta=0.20` stay fairly close to repeat `v3b`.
- The larger instability again appears late.
- At timing step `12`, both `v3c` variants are noticeably worse than repeat `v3b` on WNS:
  - `beta=0.15`: `wns_delta_vs_v3b_repeat = -0.154348`
  - `beta=0.20`: `wns_delta_vs_v3b_repeat = -0.341072`
- The largest TNS damage also appears late:
  - step `12`: `beta=0.15` has `tns_delta_vs_v3b_repeat = -26.378770`
  - step `12`: `beta=0.20` has `tns_delta_vs_v3b_repeat = -13.833580`
- `beta=0.15` extends to timing step `14` in the repeat and ends with poor timing (`TNS -116.94091`, `WNS -28.533640625`).

So the repeat trajectories do not support calling either `v3c` variant especially well-behaved on `superblue16` at this point. The instability still looks like a late-stage effect more than an early-stage one.

## Answers

### 1. Is `beta=0.20` stable enough to promote as the best current candidate?

No.

- In the original sweep run, `beta=0.20` looked best.
- In the repeat run, it regressed sharply on both TNS and WNS:
  - TNS: `-51.622550 -> -132.324990`
  - WNS: `-16.423551 -> -25.086047`
- HPWL also lost its earlier advantage relative to repeat `v3b`.

That is too large a shift to call `beta=0.20` stable enough for promotion.

### 2. Is `beta=0.15` a safer alternative?

Not based on this repeat.

- `beta=0.15` also regressed sharply on timing:
  - TNS: `-84.143690 -> -117.033870`
  - WNS: `-16.959045 -> -28.539422`
- It improved HPWL, but the timing loss is substantial.

So `beta=0.15` does not currently look like a safer alternative to `beta=0.20`.

### 3. Does `v3c` still look clearly more promising than `v3b` on `superblue16`?

No.

- Repeat `v3b` improved relative to its sweep run and remained the best timing point among the three repeated methods.
- Repeat `v3c beta=0.15` had the best HPWL, but clearly worse TNS and WNS than repeat `v3b`.
- Repeat `v3c beta=0.20` was also worse than repeat `v3b` on both TNS and WNS, and slightly worse on HPWL.

At this point, `v3c` does not look clearly more promising than `v3b` on `superblue16`.

### 4. What is the single recommended next candidate configuration?

- `DCF v3b`

Reason:

- it held up much better under the repeat check
- it delivered the best repeat TNS and best repeat WNS among the tested methods
- it stayed close on HPWL
- both `v3c` candidates showed substantial timing instability on repeat

## Conservative Conclusion

- The original `beta=0.20` sweep result now looks too unstable to trust as the best near-term candidate on `superblue16`.
- `beta=0.15` is not a safer fallback based on this repeat.
- For the current branch state and current evidence, `v3b` is the most defensible next candidate on `superblue16`.
