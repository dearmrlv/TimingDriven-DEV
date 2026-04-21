# DCF v5.2 G025 Lambda Sweep Plan

This note records the narrow v5.2 follow-up on branch `exp/dcf-v5.2-g025-lambda-sweep`.

## Scope

This is not a new method family.

It keeps the current gated hybrid form unchanged and only refines the augmentation strength:

- gate fraction fixed at `0.25`
- lambda sweep only

The hybrid form remains:

`w_hybrid = w_pin2pin * (1 + lambda * M_hat)`

inside the top-25% base Efficient-TDP gate, with base `w_pin2pin` unchanged outside the gate.

## Why This Range

The current v5.1 Stage 1 result established:

- `gate_fraction = 0.25` is the best gate setting overall
- `lambda = 0.10` is still slightly too aggressive on the blocker case `superblue16`

So the next smallest method refinement is to sweep only below `0.10`:

- `0.04`
- `0.06`
- `0.08`
- `0.10`

This range is intended to test whether a weaker augmentation can recover the remaining WNS gap without giving back too much TNS or HPWL benefit.

## Non-Goals

Do not change:

- propagation
- bins
- reverse attribution
- objective form
- tail term
- eta
- gate definition
- baseline behavior

## Execution Shape

Run only the Stage 1 cases:

- `superblue16`
- `superblue3`
- `superblue18`

Keep the existing compact first-step engagement sanity summary so the lambda sweep remains auditable.
