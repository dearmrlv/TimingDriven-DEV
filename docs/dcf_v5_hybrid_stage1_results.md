# DCF v5 Hybrid Stage 1 Results

This note records the first cautious Stage 1 check for the DCF v5 hybrid direction on branch `exp/dcf-v5-hybrid`.

## Baseline Reference

For this pass, the canonical baseline reference is `README.research.md`, as requested.

The Efficient-TDP baseline values used here are therefore:

- `superblue16`: `TNS -22.604395`, `WNS -7.841117`, `HPWL 4.726394E+08`, `runtime 319.362`
- `superblue3`: `TNS -19.854089`, `WNS -11.724317`, `HPWL 4.628147E+08`, `runtime 554.147`
- `superblue18`: `TNS -15.976826`, `WNS -6.969738`, `HPWL 2.338593E+08`, `runtime 270.556`

## What Changed

- added `docs/dcf_v5_hybrid_plan.md`
- added a new `dcf_hybrid` timing-weighting scheme
- kept Efficient-TDP pair weighting as the base signal
- added a light DCF-`M` multiplicative augmentation path:
  - intended form: `w_hybrid = w_pin2pin * (1 + lambda * M_hat)`
- added `dcf_hybrid_lambda`
- added a Stage 1 runner:
  - `scripts/run_dcf_v5_hybrid_stage1.sh`
- added a Stage 1 summarizer:
  - `scripts/summarize_dcf_v5_hybrid_stage1.py`

No propagation changes were made.
No histogram changes were made.
No objective changes were made.

## Tracked Artifacts

- `docs/artifacts/dcf_v5_hybrid_stage1_metrics.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue16_trajectory.csv`

## Stage 1 Table

| case | method | lambda | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- |
| superblue16 | Efficient-TDP | - | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 |
| superblue16 | DCF v3b | - | -1129.819360 | -45.866555 | 1.195143E+09 | 413.362 |
| superblue16 | DCF v4 | - | -58.327270 | -16.103830 | 4.663724E+08 | 390.977 |
| superblue16 | DCF v5 hybrid | 0.10 | -254.390580 | -14.251828 | 4.218739E+08 | 248.445 |
| superblue16 | DCF v5 hybrid | 0.20 | -254.390580 | -14.251828 | 4.218739E+08 | 316.711 |
| superblue16 | DCF v5 hybrid | 0.30 | -254.390580 | -14.251828 | 4.218739E+08 | 228.378 |
| superblue3 | Efficient-TDP | - | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | DCF v3b | - | -1303.412080 | -172.049531 | 2.125081E+09 | 748.897 |
| superblue3 | DCF v4 | - | -5649.634560 | -679.179938 | 3.195863E+09 | 1069.951 |
| superblue3 | DCF v5 hybrid | 0.10 | -69.585555 | -35.769992 | 4.571271E+08 | 527.974 |
| superblue3 | DCF v5 hybrid | 0.20 | -69.585555 | -35.769992 | 4.571271E+08 | 499.586 |
| superblue3 | DCF v5 hybrid | 0.30 | -69.585555 | -35.769992 | 4.571271E+08 | 497.609 |
| superblue18 | Efficient-TDP | - | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 |
| superblue18 | DCF v3b | - | -17.436737 | -6.949458 | 2.333044E+08 | 265.855 |
| superblue18 | DCF v4 | - | -17.173689 | -7.059581 | 2.332052E+08 | 264.040 |
| superblue18 | DCF v5 hybrid | 0.10 | -92.205250 | -20.069832 | 2.330831E+08 | 241.226 |
| superblue18 | DCF v5 hybrid | 0.20 | -92.205250 | -20.069832 | 2.330831E+08 | 239.388 |
| superblue18 | DCF v5 hybrid | 0.30 | -92.205250 | -20.069832 | 2.330831E+08 | 237.935 |

## Superblue16 Trajectory

Tracked artifact:

- `docs/artifacts/dcf_v5_hybrid_superblue16_trajectory.csv`

Main observations from the available trajectory rows:

- `v3b` and `v4` both produced normal timing-step summaries with nonzero exported pair counts and nonzero exported weight mass.
- The available hybrid trajectory rows do not behave like a normal active pair-weighting path:
  - `exported_pair_count = 0`
  - `total_exported_weight_mass = 0.0`
- The hybrid lambdas also remained numerically identical at the top-line metric level on all three Stage 1 cases.

So the current hybrid Stage 1 should be interpreted as a failed or non-engaged method check, not as evidence that all three lambda settings are genuinely tied.

## Answers

### 1. Does the hybrid move us closer to beating Efficient-TDP on the three key cases?

No.

- On `superblue16`, the hybrid is much worse than Efficient-TDP on TNS and WNS.
- On `superblue3`, the hybrid is still clearly worse than Efficient-TDP on both TNS and WNS, although HPWL is slightly better.
- On `superblue18`, the hybrid collapses badly on timing relative to Efficient-TDP.

### 2. Which lambda looks best?

No lambda can be credibly selected from this pass.

- `0.10`, `0.20`, and `0.30` produce identical TNS / WNS / HPWL on all three Stage 1 cases.
- That is not the behavior expected from a meaningful live lambda sweep.

### 3. Does the hybrid preserve Efficient-TDP’s WNS sharpness better than pure DCF did?

No.

- The hybrid remains far from the README Efficient-TDP WNS values on all three cases.
- On `superblue18`, it is much worse than both Efficient-TDP and the pure DCF references.

### 4. Is the result strong enough to justify a full-suite run?

No.

- The Stage 1 gate is not met.
- There is no credible evidence here that the hybrid is moving closer to beating the baseline.
- The missing / zeroed hybrid timing-step summaries strongly suggest the current hybrid path is not yet engaging as intended.

### 5. What is the single recommended next action?

- Do not run Stage 2.
- Debug the hybrid engagement path first, before spending more benchmark budget.

## Conservative Conclusion

- This Stage 1 does not justify a full-suite hybrid evaluation.
- The current hybrid implementation is not ready for method comparison, because the lambda sweep is not differentiating and the available hybrid trajectory rows show zero exported pair activity.
- The correct next action is a narrow implementation/debug pass on the hybrid composition path, not more evaluation.
