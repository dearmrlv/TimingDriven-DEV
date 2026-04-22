# DCF v5.3 G025 L004 Confirmation

This note records the narrow confirmation rerun for the current best gated-hybrid candidate on branch `exp/dcf-v5.3-g025-l004-confirm`.

Confirmed method:

- gated hybrid
- `gate_fraction = 0.25`
- `lambda = 0.04`

Compared against:

- Efficient-TDP baseline from `README.research.md`
- previous best run from `dcf_v5_2_g025_lambda_sweep`
- new confirmation rerun from `dcf_v5_3_g025_l004_confirm`

No method change was made.
No propagation change was made.
No bin change was made.
No reverse-attribution change was made.
No objective change was made.
No full-suite run was made.

## Tracked Artifacts

- `docs/artifacts/dcf_v5_3_g025_l004_confirm_metrics.csv`
- `docs/artifacts/dcf_v5_3_g025_l004_confirm_engagement_sanity.csv`
- `docs/artifacts/dcf_v5_3_superblue16_confirm_trajectory.csv`

## Did The Confirmation Rerun Engage Correctly?

Yes.

The first-step sanity table shows all three confirmation cases engaged correctly:

- `superblue16`
  - base pair count `101818`
  - gated pair count `25455`
  - actual gated fraction about `0.25`
  - exported tensor pair count `101818`
- `superblue3`
  - base pair count `44353`
  - gated pair count `11089`
  - actual gated fraction about `0.25`
  - exported tensor pair count `44353`
- `superblue18`
  - base pair count `25805`
  - gated pair count `6452`
  - actual gated fraction about `0.25`
  - exported tensor pair count `25805`

So the confirmation rerun is methodologically valid.

## Confirmation Table

| case | run | gate | lambda | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| superblue16 | baseline | - | - | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 |
| superblue16 | previous_best | 0.25 | 0.04 | -22.155895 | -7.803605 | 4.726714E+08 | 448.225 |
| superblue16 | confirm_rerun | 0.25 | 0.04 | -23.879150 | -8.048488 | 4.724991E+08 | 400.757 |
| superblue3 | baseline | - | - | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | previous_best | 0.25 | 0.04 | -21.007280 | -11.909313 | 4.627091E+08 | 774.882 |
| superblue3 | confirm_rerun | 0.25 | 0.04 | -20.849530 | -12.062613 | 4.626832E+08 | 691.870 |
| superblue18 | baseline | - | - | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 |
| superblue18 | previous_best | 0.25 | 0.04 | -16.005418 | -6.876197 | 2.346284E+08 | 299.179 |
| superblue18 | confirm_rerun | 0.25 | 0.04 | -15.923500 | -7.004612 | 2.339012E+08 | 335.111 |

## Reading The Confirmation

### superblue16

This is still the deciding case.

The confirmation rerun remains in the same neighborhood as the previous best run, but it does not reproduce the strongest previous result:

- previous best: `TNS -22.155895`, `WNS -7.803605`
- confirm rerun: `TNS -23.879150`, `WNS -8.048488`

Relative to the previous best run:

- TNS is worse by about `1.72`
- WNS is worse by about `0.245`

Relative to Efficient-TDP:

- the confirm rerun HPWL is slightly better
- but WNS is now slightly worse than the README baseline

The `superblue16` trajectory comparison also shows the two runs track each other closely in the early and mid steps, but still diverge enough in the final outcome that the previous best should not yet be treated as fully stable.

### superblue3

The candidate remains competitive, but not winning.

- previous best: `TNS -21.007280`, `WNS -11.909313`
- confirm rerun: `TNS -20.849530`, `WNS -12.062613`

So this case stays in the same approximate band, with a mild tradeoff between TNS and WNS.

### superblue18

The candidate also remains competitive, but not decisively better than baseline.

- previous best: `TNS -16.005418`, `WNS -6.876197`
- confirm rerun: `TNS -15.923500`, `WNS -7.004612`

So the rerun improves TNS but gives back some WNS and runtime.

## Answers

### 1. Did the confirmation rerun engage correctly?

Yes.

The first-step sanity summary shows a live gated path with correct gate activity on all three cases.

### 2. On `superblue16`, is the improved result stable enough to trust?

Partially, but not enough for promotion.

The rerun confirms that the candidate stays near the previous best region, so the earlier result was not a fluke caused by a dead path.

But the rerun does not reproduce the strongest prior `superblue16` timing balance closely enough to treat it as a stable promoted winner.

### 3. On `superblue3` and `superblue18`, does the candidate remain competitive?

Yes.

Both cases remain in roughly the same performance band as the previous best run, without a collapse.

But neither case gives a decisive baseline win.

### 4. Is the difference between the previous run and the confirmation rerun small enough to justify a full-suite run?

No.

The confirm rerun is not catastrophically different, but it moves enough on the blocker case `superblue16` that the evidence is still too soft for a full-suite spend.

In particular:

- the previous best `superblue16` WNS edge over baseline does not hold up cleanly
- the confirmation rerun falls back to slightly worse-than-baseline WNS
- the three-case set still does not show a stable, convincing promotion signal

### 5. What is the single recommended next action?

Do not run the full suite, and deprioritize the gated-hybrid line for now.

The line is alive and technically valid, but this confirmation step does not provide enough stability evidence to justify broader benchmark budget.

## Conservative Conclusion

- The confirmation rerun is valid and engaged.
- The `g=0.25`, `lambda=0.04` candidate remains competitive.
- But the confirmation rerun does not reproduce a strong enough stable `superblue16` result to justify promotion.
- The candidate should not yet be treated as the single full-suite choice.
- The correct next move is to avoid a full-suite run and deprioritize this line unless a new, clearly stronger idea emerges.
