# DCF v6 Local Rerank Plan

This note records the first local-rerank hypothesis on branch `exp/dcf-v6-local-rerank`.

## Goal

Test whether DCF `M` can help more safely as a local rerank or tie-break signal inside Efficient-TDP's highest-confidence pair subset, instead of as a broad weight modifier.

## What Exact Object Is Being Reranked

The reranked object is the base Efficient-TDP pin-pair dictionary built by:

- `dreamplace/ops/timing/src/net_weighting_scheme.h`
- `update_pin2pin_weight_dict(...)`

That dictionary is stored in:

- `pin2pin_base_net_weight`

inside the timing-weight update path.

This is the correct object because:

- it is the exact Efficient-TDP pair universe already used downstream
- it already carries the sharp base ranking signal
- DCF `M` is already alignable to the same pair universe in the current DCF hybrid path

## How The Local Window Is Defined

The rerank window is the top-q fraction of base pairs sorted by descending base Efficient-TDP weight.

Test only:

- top `5%`
- top `10%`
- top `20%`

All pairs outside the selected window remain untouched.

## How DCF `M` Is Used

DCF `M` is used only inside the selected local window.

For each pair in the window:

1. compute the base-rank position from the Efficient-TDP ordering
2. compute a local `M_hat` ranking on the same window
3. blend the two ranks with a fixed small mixing weight

Use a fixed first-pass strength:

- `alpha = 0.20`

This is intentionally narrow and not another broad sweep.

## What Actually Changes

There is no natural downstream truncation or export-priority hook in the current code path that would let us change ordering without changing the exported pair-weight dictionary.

So the smallest clean implementation is:

1. preserve the base pair set exactly
2. preserve all pairs outside the local window exactly
3. inside the local window only:
   - compute the reranked order
   - reuse the original window weight multiset
   - reassign those original window weights to pairs according to the reranked order

This means the intervention is a local weight permutation or local monotonic remap inside the top-ranked window, not a broad multiplicative rescaling across the design.

## Why This Is Safer Than The Previous Hybrid Line

This is smaller and safer than the previous gated-hybrid line because:

- Efficient-TDP defines the full candidate set unchanged
- Efficient-TDP defines the global ordering unchanged outside the local window
- DCF `M` only acts as a local ordering refinement within a small top-ranked prefix
- the rest of the pair universe is untouched
- no new propagation, histogram, reverse-attribution, or objective changes are required

So the v6 local-rerank line is explicitly designed to preserve Efficient-TDP sharpness first, and let DCF influence only the most trusted portion of the ranking.
