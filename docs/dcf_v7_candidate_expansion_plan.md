# DCF v7 Candidate Expansion Plan

This note records the first candidate-expansion hypothesis on branch `exp/dcf-v7-candidate-expansion`.

## Goal

Test whether DCF `M` can help more safely as a small supplementary pair proposal mechanism while leaving Efficient-TDP's original selected pair set and original pair weights untouched.

## Base Candidate Set

Let:

- `P_base` = the Efficient-TDP pin-pair dictionary built by `update_pin2pin_weight_dict(...)`
- `w_base` = the original Efficient-TDP pair weights in that dictionary

For v7:

- keep `P_base` unchanged
- keep every `w_base` entry unchanged

## What Counts As A Supplementary Pair

A supplementary pair is:

- a DCF-aligned net-arc pair with nonzero mapped `M`
- not already present in `P_base`

This differs from the previous hybrid and rerank lines, which only used pairs already present in the base dictionary.

## How Expansion Size Is Defined

Expansion size is defined relative to the base pair count:

- `+1%`
- `+2%`
- `+5%`

That means if `|P_base| = N`, then the target supplementary set size is `ceil(f * N)`.

## How Supplementary Pairs Are Proposed

Use DCF `M` exactly as before to build an aligned pair-mass map from timing arcs.

Then:

1. collect all DCF-supported pairs with nonzero mapped mass
2. exclude any pair already in `P_base`
3. rank the remaining pairs by descending `M_hat`
4. take only the top supplementary count for the requested expansion size

This keeps the proposal rule explicit and narrow.

## How Supplementary Weights Are Assigned

Use one fixed conservative weighting rule for the first pass:

- assign every supplementary pair the 10th-percentile base weight

If the base distribution is degenerate, this falls back naturally to a small base-like weight.

This is intentionally conservative:

- supplementary pairs are extra hints
- they should not dominate the original Efficient-TDP set
- no existing base weight is modified

## Why This Is Safer Than Hybrid Or Rerank

This is safer than the previous two families because:

- the original base pair set is preserved intact
- the original base weights are preserved intact
- no existing base ordering is changed
- DCF only contributes a small number of extra candidate pairs
- the extra pairs receive conservative low weights

So v7 treats DCF as a proposal or discovery signal rather than a broad weighting or ranking modifier.
