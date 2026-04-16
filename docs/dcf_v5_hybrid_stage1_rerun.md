# DCF v5 Hybrid Stage 1 Rerun

This note records the clean rerun of the DCF v5 hybrid Stage 1 check on branch `exp/dcf-v5-hybrid` after rebuilding the runtime and revalidating the hybrid engagement path.

Scope:

- cases:
  - `superblue16`
  - `superblue3`
  - `superblue18`
- comparison methods:
  - Efficient-TDP baseline from `README.research.md`
  - `dcf_v3b`
  - `dcf_v4`
  - `dcf_v5_hybrid_l010`
  - `dcf_v5_hybrid_l020`
  - `dcf_v5_hybrid_l030`
- output tag:
  - `dcf_v5_hybrid_stage1_rerun`

No hybrid formula change was made.
No propagation change was made.
No bin change was made.
No objective change was made.
No full-suite Stage 2 run was made.

## Tracked Artifacts

- `docs/artifacts/dcf_v5_hybrid_stage1_metrics.csv`
- `docs/artifacts/dcf_v5_hybrid_stage1_engagement_sanity.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue16_trajectory.csv`

## Why This Rerun Is Trustworthy

Each hybrid run now carries a compact first-step engagement sanity row from `debug_summary.json` only.

For every `case/lambda` combination, the tracked sanity table shows:

- nonzero base pin2pin pair count
- nonzero mapped `M_hat` pair count
- nonzero final hybrid pair count
- nonzero exported tensor pair count
- lambda-dependent final and exported total weight mass
- lambda-dependent top pair weight after export

Examples from `docs/artifacts/dcf_v5_hybrid_stage1_engagement_sanity.csv`:

- `superblue16`
  - exported total mass rises from `1034707.1875` at `0.10` to `1035062.0` at `0.30`
  - top pair weight rises from `33.0` to `39.0`
- `superblue3`
  - exported total mass rises from `455153.0` at `0.10` to `457288.5` at `0.30`
  - top pair weight rises from `35.5966` to `42.0358`
- `superblue18`
  - exported total mass rises from `268925.09375` at `0.10` to `269849.03125` at `0.30`
  - top pair weight rises from `55.0` to `65.0`

So this rerun should be treated as a valid hybrid method comparison, unlike the earlier stale/non-engaged Stage 1 pass.

## Stage 1 Table

| case | method | lambda | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- |
| superblue16 | Efficient-TDP | - | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 |
| superblue16 | DCF v3b | - | -1225.894240 | -46.501246 | 1.206730E+09 | 353.094 |
| superblue16 | DCF v4 | - | -1701.940960 | -47.952473 | 1.251260E+09 | 371.817 |
| superblue16 | DCF v5 hybrid | 0.10 | -17.382887 | -12.364184 | 4.638303E+08 | 443.169 |
| superblue16 | DCF v5 hybrid | 0.20 | -19.920288 | -23.250348 | 4.636246E+08 | 447.309 |
| superblue16 | DCF v5 hybrid | 0.30 | -20.068239 | -16.058911 | 4.635145E+08 | 461.036 |
| superblue3 | Efficient-TDP | - | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | DCF v3b | - | -154.419080 | -42.022637 | 1.028749E+09 | 598.386 |
| superblue3 | DCF v4 | - | -2137.769760 | -241.284875 | 2.227109E+09 | 711.641 |
| superblue3 | DCF v5 hybrid | 0.10 | -20.829390 | -11.871647 | 4.628359E+08 | 655.028 |
| superblue3 | DCF v5 hybrid | 0.20 | -21.047935 | -11.884948 | 4.626482E+08 | 640.096 |
| superblue3 | DCF v5 hybrid | 0.30 | -20.061879 | -11.669104 | 4.626172E+08 | 640.373 |
| superblue18 | Efficient-TDP | - | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 |
| superblue18 | DCF v3b | - | -17.539333 | -7.230634 | 2.333601E+08 | 260.365 |
| superblue18 | DCF v4 | - | -17.294665 | -6.898852 | 2.333973E+08 | 257.448 |
| superblue18 | DCF v5 hybrid | 0.10 | -15.905527 | -6.886202 | 2.346556E+08 | 294.325 |
| superblue18 | DCF v5 hybrid | 0.20 | -16.644815 | -7.100224 | 2.340321E+08 | 295.922 |
| superblue18 | DCF v5 hybrid | 0.30 | -16.821959 | -7.321099 | 2.357755E+08 | 264.010 |

## Case Reading

### superblue16

The hybrid no longer looks broken, but it still does not beat Efficient-TDP.

- all three hybrid lambdas engage cleanly
- hybrid improves sharply over pure DCF references on HPWL and TNS
- hybrid still misses Efficient-TDP badly on WNS
- `0.10` is the best hybrid setting here

### superblue3

This case is close but not a clean win.

- all three hybrid lambdas engage cleanly
- `0.30` is the best hybrid setting here
- `0.30` nearly matches Efficient-TDP TNS and slightly improves WNS and HPWL
- the TNS remains slightly worse than Efficient-TDP, so this is near-parity rather than a decisive beat

### superblue18

This is the strongest hybrid result in the rerun.

- all three hybrid lambdas engage cleanly
- `0.10` beats Efficient-TDP on both TNS and WNS
- that timing gain comes with worse HPWL and slower runtime than the README baseline
- larger lambdas degrade timing on this case

## Answers

### 1. Did the rerun actually engage the hybrid path on all three cases?

Yes.

The tracked engagement sanity summary shows nonzero base, mapped `M_hat`, final hybrid, and exported tensor activity for every hybrid run in the rerun.

### 2. Are the lambda variants now producing genuinely different exported weights?

Yes.

For every case, the first-step exported tensor total mass and top pair weight change monotonically across `0.10`, `0.20`, and `0.30`.

### 3. On valid rerun results, does the hybrid move us closer to beating Efficient-TDP?

Mixed.

- `superblue16`: no; still clearly worse because WNS remains much weaker
- `superblue3`: mostly yes; `0.30` reaches near-parity and slightly improves WNS and HPWL, but TNS is still a little worse
- `superblue18`: yes; `0.10` is better than Efficient-TDP on both TNS and WNS, though HPWL is worse

### 4. Which lambda looks best right now?

`0.10` looks best overall.

- it is the best hybrid choice on `superblue16`
- it is the best hybrid choice on `superblue18`
- `0.30` is best only on `superblue3`

So `0.10` is the safest current default if a single lambda must be chosen for the next gate.

### 5. Is the evidence now strong enough to justify a full-suite run?

Not yet.

The rerun is now valid, but the evidence is still too uneven:

- one case is clearly promising (`superblue18`)
- one case is near-parity but not a clean win (`superblue3`)
- one case still misses the baseline materially on WNS (`superblue16`)

That is enough to keep the hybrid direction alive, but not enough yet for a confident Stage 2 full-suite spend.

## Conservative Conclusion

- The rerun is valid and auditable.
- The hybrid path engaged on all three cases.
- The lambda sweep now genuinely changes exported hybrid weights.
- The earlier identical-lambda Stage 1 result should remain classified as invalid stale runtime behavior.
- `lambda=0.10` is the best overall setting from this rerun.
- The direction is promising enough to continue, but not yet strong enough for a full-suite run without another narrow decision step.
