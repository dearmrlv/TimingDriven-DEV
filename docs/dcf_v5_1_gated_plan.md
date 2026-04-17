# DCF v5.1 Gated Hybrid Plan

This note records the narrow implementation plan for the gated DCF v5.1 hybrid experiment on branch `exp/dcf-v5.1-gated-hybrid`.

## Goal

Keep the existing hybrid form:

`w_hybrid = w_pin2pin * (1 + lambda * M_hat)`

with:

- `lambda = 0.10`

but only apply the DCF `M_hat` augmentation to the top-q fraction of base Efficient-TDP pairs.

Test only:

- `q = 0.10`
- `q = 0.25`
- `q = 0.50`

## Where The Base Ranking Is Available

The base Efficient-TDP pair dictionary is already materialized in the existing hybrid implementation path at:

- `dreamplace/ops/timing/src/net_weighting_scheme.h`

inside:

- `NetWeighting<T, NetWeightingScheme::DCF_HYBRID>`

The base pair weights are stored in:

- `pin2pin_base_net_weight`

That dictionary is built before any DCF hybrid augmentation is applied, so it is the correct source for the gate ranking.

## Where The Gate Is Formed

The gate should be formed inside the same `DCF_HYBRID` specialization, immediately after the base dictionary is available and before the final hybrid writeback loop.

The gate is defined by:

1. enumerating all base pin-pair entries from `pin2pin_base_net_weight`
2. sorting them by descending base `w_pin2pin`
3. selecting the top-q fraction by pair count

Tie-breaks should be deterministic, using the pin ids after weight.

## Where The Gated Augmentation Is Applied

The gated augmentation should also happen inside the existing final export loop in `DCF_HYBRID`.

For pairs inside the gate:

- apply `w_pin2pin * (1 + lambda * M_hat)`

For pairs outside the gate:

- keep `w_pin2pin`

This keeps the gate logic local to the existing hybrid composition point and avoids touching downstream objective code.

## Why This Is The Smallest Clean Intervention

This approach is the smallest clean change because:

- the base Efficient-TDP pair ranking is already present there
- the mapped DCF `M_hat` values are already present there
- the final exported pair dictionary is already written there
- no propagation logic needs to move
- no objective logic needs to move
- no new heavyweight diagnostics path is needed

Only one new control is required:

- `dcf_hybrid_gate_fraction`

The rest of the implementation can reuse the current v5 hybrid path, current compact first-step debug summary path, and the current Stage 1 experiment pattern.
