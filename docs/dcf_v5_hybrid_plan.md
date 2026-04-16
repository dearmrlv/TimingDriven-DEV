# DCF v5 Hybrid Plan

This note documents the smallest clean intervention point for a first hybrid between Efficient-TDP and DCF.

## Base Pin2Pin Weight

The base Efficient-TDP pair weight comes from the existing `pin2pin` timing-weighting scheme in:

- `dreamplace/ops/timing/src/net_weighting_scheme.h`

That scheme populates the shared dictionary:

- `placedb.pin2pin_net_weight`

The objective already consumes that dictionary without any special-case logic in:

- `dreamplace/PlaceObj.py`
- `dreamplace/ops/pin2pin_attraction/pin2pin_attraction.py`

## DCF M Signal

The DCF shared-mass signal `M` is already computed naturally in the DCF export path from the reverse-propagated arc histogram. In the current code, `M` is the per-arc `total_mass` value derived from:

- `arc_hist`
- `dcf_hist_mass(hist)`

inside:

- `dreamplace/ops/timing/src/net_weighting_scheme.h`

## Hybrid Combination Point

The smallest clean combination point is the shared pin-pair weight dictionary right before the existing pin-to-pin attraction objective sees it.

Operationally, the hybrid path should:

1. build the normal Efficient-TDP `pin2pin` weights
2. compute DCF `M` on the same timing step
3. map that `M` onto the already-existing pair dictionary
4. write the final hybridized weights into the same output dictionary used by the objective

## Why This Is The Smallest Clean Intervention

- it keeps the placement objective unchanged
- it keeps DCF propagation unchanged
- it keeps the histogram machinery unchanged
- it keeps baseline `pin2pin` unchanged
- it keeps DCF v3/v4 intact and recoverable
- it reuses the existing pair handoff path instead of introducing a new optimization term

## One Extra Internal Detail

The hybrid must preserve a clean Efficient-TDP base across timing steps.

Because `pin2pin` weights are updated incrementally over time, the hybrid path cannot safely overwrite the same dictionary in place and then reuse that hybridized dictionary as the next step's base. To avoid compounding the augmentation, the hybrid path uses one separate internal base dictionary for the raw pin2pin weights, and then writes the augmented values into the normal output dictionary consumed by the objective.

## First Hybrid Form

The first hybrid uses the preferred minimal multiplicative form:

- `w_hybrid = w_pin2pin * (1 + lambda * M_hat)`

with:

- `M_hat = M / max(M)` over the mapped pair universe for the current timing step

This keeps the correction bounded, stable, and easy to interpret.
