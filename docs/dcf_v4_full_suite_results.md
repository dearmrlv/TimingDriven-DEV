# DCF v4 Full-Suite Results

This note records the next narrow method iteration after DCF v3 on branch `exp/dcf-v4`.

## What Changed

DCF v4 keeps the DCF v3 backbone intact:

- no `eta`
- `M` as the base utility
- same all-arcs reverse propagation
- same histogram bins
- same pin-pair export path
- same pin-to-pin attraction objective

The only method change is the tail-term schedule.

## DCF v4 Definition

DCF v4 uses:

- `U = M + beta_eff(step) * T`
- `w = log(1 + U)`

with defaults:

- `dcf_v4_base_beta = 0.20`
- `dcf_v4_decay_start_step = 7`
- `dcf_v4_decay_end_step = 10`

Operationally:

- timing steps `1` to `6`: `beta_eff = 0.20`
- timing steps `7` to `10`: `beta_eff` decays linearly from `0.20` to `0.00`
- timing step `11` and later: `beta_eff = 0.00`

So early steps behave like `v3c beta=0.20`, while later steps move back toward `v3b`-like behavior.

## Files Changed

- `dreamplace/params.json`
  - added:
    - `dcf_v4_base_beta`
    - `dcf_v4_decay_start_step`
    - `dcf_v4_decay_end_step`
- `dreamplace/BasicPlace.py`
- `dreamplace/ops/timing/timing.py`
- `dreamplace/ops/timing/src/timing_cpp.h`
- `dreamplace/ops/timing/src/timing_cpp.cpp`
- `dreamplace/ops/timing/src/net_weighting_scheme.h`
  - plumbed `v4` and applied the step-dependent tail decay inside the existing export utility path
- `scripts/run_dcf_full_suite.sh`
  - added a parameterized full-suite DCF runner that starts from the existing `pin2pin` case configs
- `scripts/summarize_dcf_v4_full_suite.py`
  - added a small summarizer for tracked CSV artifacts

No baseline config family was modified.
No DCF v3 behavior was removed.

## What Was Run

- Reused existing full-suite `Efficient-TDP` baseline metrics from `results/baselines/efficient_tdp/`
  - baseline behavior is unchanged on this branch
- Fresh full-suite runs on all 8 ICCAD2015 cases for:
  - `DCF v3b`
  - `DCF v3c beta=0.20`
  - `DCF v4`

Cases:

- `superblue1`
- `superblue3`
- `superblue4`
- `superblue5`
- `superblue7`
- `superblue10`
- `superblue16`
- `superblue18`

Tracked artifacts:

- `docs/artifacts/dcf_v4_full_suite_metrics.csv`
- `docs/artifacts/dcf_v4_full_suite_summary.csv`
- `docs/artifacts/dcf_v4_superblue16_trajectory.csv`

## Full-Suite Result Table

| case | method | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- |
| superblue1 | Efficient-TDP | -665.092760 | -48.121187 | 4.526704E+08 | 134.414 |
| superblue1 | DCF v3b | -43.767775 | -20.161828 | 4.183046E+08 | 341.012 |
| superblue1 | DCF v3c beta=0.20 | -43.857940 | -16.753484 | 4.171731E+08 | 365.517 |
| superblue1 | DCF v4 | -43.142940 | -16.223541 | 4.171756E+08 | 364.106 |
| superblue3 | Efficient-TDP | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | DCF v3b | -6494.606080 | -1211.047250 | 3.164240E+09 | 601.495 |
| superblue3 | DCF v3c beta=0.20 | -20668.750080 | -619.689813 | 4.893294E+09 | 627.154 |
| superblue3 | DCF v4 | -1757.364800 | -288.876875 | 2.450572E+09 | 578.750 |
| superblue4 | Efficient-TDP | -90.259830 | -9.161039 | 3.180224E+08 | 1324.106 |
| superblue4 | DCF v3b | -158.445700 | -10.184970 | 3.213130E+08 | 314.009 |
| superblue4 | DCF v3c beta=0.20 | -173.576060 | -9.956221 | 3.204704E+08 | 312.320 |
| superblue4 | DCF v4 | -134.615940 | -10.593377 | 3.199714E+08 | 312.805 |
| superblue5 | Efficient-TDP | -65.440080 | -24.220008 | 4.852562E+08 | 748.797 |
| superblue5 | DCF v3b | -94.266510 | -35.770289 | 4.908384E+08 | 455.823 |
| superblue5 | DCF v3c beta=0.20 | -126.186870 | -26.200203 | 4.949856E+08 | 441.631 |
| superblue5 | DCF v4 | -78.269960 | -26.437191 | 4.941714E+08 | 441.891 |
| superblue7 | Efficient-TDP | -37.190520 | -15.395518 | 5.980916E+08 | 757.736 |
| superblue7 | DCF v3b | -50.475740 | -15.395518 | 5.949848E+08 | 628.924 |
| superblue7 | DCF v3c beta=0.20 | -51.056535 | -15.395518 | 5.950458E+08 | 627.235 |
| superblue7 | DCF v4 | -50.782045 | -15.395518 | 5.950358E+08 | 624.595 |
| superblue10 | Efficient-TDP | -564.221600 | -23.441709 | 9.145873E+08 | 1866.491 |
| superblue10 | DCF v3b | -597.703240 | -42.213734 | 9.143126E+08 | 633.807 |
| superblue10 | DCF v3c beta=0.20 | -601.848280 | -42.465621 | 9.158918E+08 | 607.297 |
| superblue10 | DCF v4 | -614.959360 | -42.462918 | 9.140662E+08 | 632.299 |
| superblue16 | Efficient-TDP | -95.195720 | -12.571035 | 4.602074E+08 | 89.073 |
| superblue16 | DCF v3b | -94.263520 | -17.942543 | 4.658729E+08 | 339.012 |
| superblue16 | DCF v3c beta=0.20 | -60.500040 | -17.556723 | 4.656717E+08 | 337.359 |
| superblue16 | DCF v4 | -74.025235 | -23.177670 | 4.660245E+08 | 337.941 |
| superblue18 | Efficient-TDP | -19.338465 | -6.613083 | 1.704546E+08 | 74.420 |
| superblue18 | DCF v3b | -17.383956 | -7.021271 | 2.332455E+08 | 250.522 |
| superblue18 | DCF v3c beta=0.20 | -17.286258 | -7.021872 | 2.333622E+08 | 250.478 |
| superblue18 | DCF v4 | -17.268469 | -7.078376 | 2.332768E+08 | 250.248 |

## Aggregate Summary

From `docs/artifacts/dcf_v4_full_suite_summary.csv`:

- `v4` beats `v3b` on TNS in `6 / 8` cases
- `v4` beats `v3b` on WNS in `3 / 8` cases
- `v4` beats `v3c beta=0.20` on TNS in `6 / 8` cases
- `v4` beats `v3c beta=0.20` on WNS in `3 / 8` cases
- `v4` beats `v3b` on HPWL in `4 / 8` cases
- mean runtime:
  - `v3b`: `445.575 s`
  - `v3c beta=0.20`: `446.124 s`
  - `v4`: `442.829 s`

So runtime is effectively neutral across the DCF variants in this pass.

## Superblue16 Trajectory

Tracked artifact:

- `docs/artifacts/dcf_v4_superblue16_trajectory.csv`

Main observations:

- `v4` largely tracks `v3b` in the early timing steps, as intended.
- On `superblue16`, the late-stage decay did not recover WNS relative to `v3c beta=0.20`.
- By later steps, `v4` still shows poor WNS on this case and does not deliver the hoped-for `v3c`-like TNS with `v3b`-like late stability.

## Interpretation

### v4 vs v3c beta=0.20

- `v4` clearly improves on `v3c beta=0.20` in several cases that look unstable or over-aggressive:
  - especially `superblue3`, where both timing and HPWL improve dramatically
  - also `superblue5` and `superblue7` on TNS / HPWL balance
- But `v4` does not consistently improve WNS relative to `v3c beta=0.20`.
  - It wins WNS in only `3 / 8` cases.
  - On `superblue16`, WNS is materially worse than `v3c beta=0.20`.

### v4 vs v3b

- `v4` improves TNS relative to `v3b` in `6 / 8` cases.
- But it improves WNS relative to `v3b` in only `3 / 8` cases.
- The strongest win is `superblue3`, where `v4` is far better than both `v3b` and `v3c beta=0.20`.
- The most important miss is `superblue16`, where `v4` is worse than `v3b` on both WNS and HPWL.

### Did Late-Stage Tail Decay Help?

- Partially.
- The schedule appears to tame some of the fixed-beta damage seen in `v3c beta=0.20`, particularly on `superblue3`.
- But it does not reliably solve the late-stage tradeoff on `superblue16`.
- So the simple decay schedule is directionally useful, but not sufficient to call the problem solved.

## Answers

### 1. Does DCF v4 improve the late-stage WNS behavior relative to v3c beta=0.20?

Only partially.

- Across the suite, `v4` improves WNS over `v3c beta=0.20` in `3 / 8` cases.
- It does not improve WNS on the key `superblue16` case.

### 2. Does DCF v4 preserve most of the TNS / HPWL benefit of v3c beta=0.20?

Often yes on TNS, but not consistently on HPWL.

- `v4` beats `v3c beta=0.20` on TNS in `6 / 8` cases.
- HPWL is mixed and case-dependent.
- On `superblue16`, `v4` loses both TNS and HPWL relative to `v3c beta=0.20`.

### 3. Across the full benchmark suite, is DCF v4 a better overall candidate than v3b?

Not clearly.

- It has better TNS in most cases.
- But it does not deliver correspondingly better WNS.
- The `superblue16` regression against `v3b` is still important enough to block a clear promotion.

### 4. Is superblue16 still the outlier that determines the tradeoff, or does the full suite support the same direction?

- `superblue16` remains the main tradeoff case.
- The full suite does show that late-stage tail decay can help elsewhere, especially on `superblue3`.
- But the full suite does not overturn the `superblue16` concern strongly enough to make `v4` the obvious next default.

### 5. Based on the full-suite results, should DCF v4 become the default next candidate?

No, not yet.

## Conservative Conclusion

- DCF v4 is a meaningful improvement over fixed `v3c beta=0.20` in some difficult cases.
- The late-stage decay idea looks useful and worth keeping.
- But the current simple schedule is not strong enough to replace `v3b` as the default next candidate across the suite.
- `superblue16` still blocks that promotion.

## Recommended Next Action

- Keep `v3b` as the safest current reference candidate.
- Treat `v4` as the most promising follow-up direction, but do one more narrow schedule check before promoting it.

In other words:

- do not make `v4` the default next candidate yet
- do keep the late-stage tail-decay direction as the next thing to refine
