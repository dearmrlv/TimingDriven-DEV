# DCF v3 Initial Results

This note records the first implementation-and-evaluation pass for DCF v3 on branch `exp/dcf-v3`.

## What Changed

- `dreamplace/params.json`
  - added DCF-only export controls:
    - `dcf_version`
    - `dcf_beta`
- `dreamplace/BasicPlace.py`
- `dreamplace/ops/timing/timing.py`
- `dreamplace/ops/timing/src/timing_cpp.h`
- `dreamplace/ops/timing/src/timing_cpp.cpp`
  - plumbed the new DCF-only export controls through the existing timing operator
- `dreamplace/ops/timing/src/net_weighting_scheme.h`
  - kept the current DCF propagation, reverse pass, histogram construction, and pin-pair handoff intact
  - changed only the exported utility mapping for explicit DCF v3 selections
- `test/iccad2015.dcfv3/`
  - added `superblue16` and `superblue18` configs for `v3a`, `v3b`, and `v3c`
- `scripts/run_dcf_v3_experiments.sh`
  - added a small experiment runner for `v1`, `v3a`, `v3b`, and `v3c`
- `scripts/collect_experiment_metrics.py`
  - added a small metrics extractor for the experiment outputs

No DREAMPlace 4.0 baseline behavior changed.
No Efficient-TDP baseline behavior changed.
The existing DCF v1 path remains the default when `net_weighting_scheme: "dcf"` is used without an explicit `dcf_version` override.

## Variant Definitions

- `v1`
  - `U = S + 0.5 * T`
  - `w = log(1 + U * eta)`
- `v3a`
  - `U = S + 0.5 * T`
  - `w = log(1 + U)`
- `v3b`
  - `U = M`
  - `w = log(1 + U)`
- `v3c`
  - `U = M + beta * T`
  - `beta = 0.25` in this pass
  - `w = log(1 + U)`

All three v3 variants keep:

- all-arc DCF propagation
- the same reverse attribution rule
- the same histogram bins
- the same timing integration point
- the same pin-to-pin attraction consumer
- the same EMA smoothing after the mapped weight

## Configs Added

- `test/iccad2015.dcfv3/superblue16.v3a.json`
- `test/iccad2015.dcfv3/superblue16.v3b.json`
- `test/iccad2015.dcfv3/superblue16.v3c.json`
- `test/iccad2015.dcfv3/superblue18.v3a.json`
- `test/iccad2015.dcfv3/superblue18.v3b.json`
- `test/iccad2015.dcfv3/superblue18.v3c.json`

## What Was Run

- Reused existing baseline metrics for:
  - DREAMPlace 4.0
  - Efficient-TDP
- Re-ran DCF `v1` on this branch for apples-to-apples comparison
- Ran DCF `v3a`, `v3b`, and `v3c`

Staged execution:

- Stage 1: `superblue18`
- Stage 2: `superblue16`
- Stage 3: not run

Lightweight timing-step summaries were enabled for the DCF runs to preserve:

- `exported_pair_count`
- `total_exported_weight_mass`
- average / median exported pair length
- timing-step runtime

No fresh heavy replay / pair-dump campaign was run in this pass.

## superblue18

| method | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- |
| DREAMPlace 4.0 | -47.919910 | -11.780133 | 2.065470E+09 | 244.688 |
| Efficient-TDP | -19.338465 | -6.613083 | 1.704546E+08 | 74.420 |
| DCF v1 | -17.710421 | -7.176290 | 2.374021E+08 | 218.351 |
| DCF v3a | -18.467321 | -7.071814 | 2.360729E+08 | 205.699 |
| DCF v3b | -17.733509 | -6.611638 | 2.342526E+08 | 217.755 |
| DCF v3c | -17.279637 | -6.923382 | 2.333595E+08 | 229.403 |

Final timing-step summary signals:

| method | timing step | exported pairs | total weight mass | avg length | median length | timing update (s) | DCF pass (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DCF v1 | 14 | 57379 | 252185.0902 | 608.7003 | 77.1957 | 10.7668 | 1.570 |
| DCF v3a | 13 | 61580 | 213031.5998 | 575.1160 | 80.3878 | 11.3430 | 1.545 |
| DCF v3b | 14 | 62365 | 89203.1288 | 566.9284 | 72.2717 | 11.4074 | 1.551 |
| DCF v3c | 15 | 61687 | 88698.0751 | 567.1789 | 69.1301 | 10.8637 | 1.610 |

## superblue16

| method | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- |
| DREAMPlace 4.0 | -64.993815 | -14.681975 | 1.677648E+09 | 292.204 |
| Efficient-TDP | -95.195720 | -12.571035 | 4.602074E+08 | 89.073 |
| DCF v1 | -70.678170 | -15.385641 | 4.860227E+08 | 221.847 |
| DCF v3a | -83.145615 | -18.457400 | 4.705998E+08 | 221.876 |
| DCF v3b | -84.329670 | -22.316639 | 4.397109E+08 | 219.968 |
| DCF v3c | -54.797445 | -23.348156 | 4.394180E+08 | 220.508 |

Final timing-step summary signals:

| method | timing step | exported pairs | total weight mass | avg length | median length | timing update (s) | DCF pass (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DCF v1 | 13 | 220539 | 1271540.7615 | 878.9043 | 127.4275 | 12.1646 | 2.463 |
| DCF v3a | 13 | 188925 | 758548.0795 | 892.2326 | 118.2891 | 11.3260 | 2.324 |
| DCF v3b | 13 | 188173 | 358798.3382 | 825.6145 | 86.8959 | 11.1896 | 2.310 |
| DCF v3c | 13 | 172020 | 322567.3822 | 845.1168 | 89.7235 | 11.2789 | 2.318 |

## Interpretation

- `v3a` confirms that removing `eta` materially changes the exported signal.
  - The total exported weight mass drops immediately on both cases.
  - The final quality impact is mixed.
  - On `superblue18`, `v3a` slightly improves WNS and HPWL relative to `v1`, but slightly worsens TNS.
  - On `superblue16`, `v3a` improves HPWL but degrades both TNS and WNS relative to `v1`.
- `v3b` helps more than `v3a` on `superblue18` for timing alignment.
  - `v3b` reaches the best WNS of the DCF variants on `superblue18` (`-6.611638`), essentially matching the reused Efficient-TDP baseline WNS.
  - `v3b` also reduces HPWL relative to `v1` and `v3a`.
- `v3b` does not improve timing over `v3a` on `superblue16` in this initial run.
  - It improves HPWL substantially (`4.397109E+08` vs `4.705998E+08`),
  - but both TNS and WNS are worse than `v3a`.
- `v3c` gives the strongest HPWL on both cases in this initial pass.
  - On `superblue18`, it has the best TNS and HPWL among the DCF variants, while WNS is not as strong as `v3b`.
  - On `superblue16`, it gives the best TNS and best HPWL among the DCF variants, but also the worst WNS.

So the current hypothesis is only partially supported by this first full-run test:

- removing `eta` clearly changes the behavior, but does not yield an immediate across-the-board timing gain by itself
- switching from `S + 0.5T` to `M` helps on `superblue18`, but not on `superblue16` in this initial full run
- adding a light `T` tail to `M` helps TNS and HPWL in both cases, but it does not improve WNS in this first pass

## What To Test Next

- Re-run `superblue16` once more for `v1`, `v3b`, and `v3c` to check whether the observed ordering is stable on this case.
- Inspect the timing-step trajectories for `superblue16`, not just the final row, to see when `v3b` and `v3c` diverge in exported pair count and weight mass.
- If the `superblue16` ordering is stable, test `superblue1` next as the optional Stage 3 case.
- If we need one more narrow follow-up after that, sweep only `beta` for `v3c` around the initial point rather than changing the propagation framework.
