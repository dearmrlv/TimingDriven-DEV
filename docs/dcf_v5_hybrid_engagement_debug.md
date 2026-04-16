# DCF v5 Hybrid Engagement Debug

This note records the narrow first-step engagement debug for the DCF v5 hybrid path on branch `exp/dcf-v5-hybrid`.

Scope:

- case: `superblue18`
- timing step: `1`
- lambdas:
  - `0.10`
  - `0.20`
  - `0.30`

No broad evaluation was run here.
No hybrid formula change was made.

## Tracked Artifacts

- `docs/artifacts/dcf_v5_hybrid_superblue18_base_pairs_step1.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue18_mhat_pairs_step1.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue18_final_pairs_l010_step1.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue18_final_pairs_l020_step1.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue18_final_pairs_l030_step1.csv`
- `docs/artifacts/dcf_v5_hybrid_superblue18_debug_summary.json`

## What The Debug Shows

### 1. Is the raw base pin2pin dictionary nonzero?

Yes.

From `docs/artifacts/dcf_v5_hybrid_superblue18_debug_summary.json`:

- raw base pair count: `25805`
- raw base total weight mass: about `268460.9`
- raw base top weight: `50.0`

So the Efficient-TDP base signal is alive before any DCF augmentation.

### 2. Is DCF `M` nonzero and mapped?

Yes.

From the same summary:

- mapped `M_hat` nonzero pair count: `20277`
- mapped `M_hat` total mass source: `1081502592.0`
- top normalized `M_hat` values include `1.0`

So the DCF shared-mass signal is also alive and mapped onto a large subset of the base pair universe.

### 3. Is the final hybrid dictionary nonzero?

Yes.

Per lambda:

- `lambda=0.10`
  - final pair count: `25805`
  - total weight mass: `268923.5`
  - max weight: `55.0`
- `lambda=0.20`
  - final pair count: `25805`
  - total weight mass: `269386.2`
  - max weight: `60.0000038`
- `lambda=0.30`
  - final pair count: `25805`
  - total weight mass: `269848.9`
  - max weight: `65.0`

So the final hybrid dictionary is alive and clearly lambda-dependent.

### 4. Does it remain nonzero at the exported tensor view?

Yes.

The exported tensor view matches the final hybrid dictionary at step 1:

- `lambda=0.10`: pair count `25805`, total mass `268923.5`
- `lambda=0.20`: pair count `25805`, total mass `269386.1875`
- `lambda=0.30`: pair count `25805`, total mass `269848.90625`

So on this focused debug run, the signal does **not** disappear between dictionary writeback and tensor export.

## Where The Earlier Failure Came From

The current debug run shows that the hybrid chain is alive at step 1.

That means the earlier Stage 1 result with:

- identical metrics across all three lambdas
- `exported_pair_count = 0`
- `total_exported_weight_mass = 0.0`

was not caused by the intended hybrid formula collapsing inside the live step-1 path.

The most direct observed cause was earlier non-engaged execution from stale runtime / signature mismatch conditions:

- earlier logs showed repeated `unsupported net-weighting scheme 'dcf_hybrid'`
- later debug reruns exposed a binding signature mismatch before the timing step could complete

So the prior “all lambdas identical” result came from invalid or stale runs, not from this live step-1 hybrid chain.

## Answers

### 1. Is the raw base pin2pin dictionary nonzero?

Yes.

### 2. Is DCF `M` nonzero and mapped?

Yes.

### 3. Is the final hybrid dictionary nonzero?

Yes.

### 4. If yes, where does it become zero later?

It does not become zero in the current first-step debug chain.

- raw base dict: nonzero
- mapped `M_hat`: nonzero
- final hybrid dict: nonzero
- exported tensor view: nonzero

So there is no zeroing point inside the live first-step path for this case.

### 5. If no, at what exact stage does it fail?

Not applicable for the current debug run.

### 6. Why do all three lambdas currently produce identical results?

They do **not** in the live first-step debug path.

The current debug artifacts show clear lambda differentiation in:

- final hybrid total weight mass
- top final pair weights
- exported tensor total mass

Therefore the earlier identical-lambda Stage 1 result was due to invalid stale / non-engaged runs, not because the current hybrid composition mathematically collapsed the lambdas.

### 7. What is the smallest code fix likely needed next?

The next smallest fix is not a hybrid-formula change.

It is to cleanly rerun the Stage 1 hybrid experiments from a known-good rebuilt runtime, with stale outputs removed or isolated, so the evaluation artifacts reflect the now-confirmed live hybrid path.

In short:

- the engagement path itself is alive
- the evaluation pipeline previously consumed invalid results
- the next step should be a clean re-run of the Stage 1 hybrid evaluation, not another formula change

## Conservative Conclusion

- The DCF v5 hybrid path is alive on `superblue18` step 1.
- The hybrid chain is connected end-to-end:
  - base pin2pin dict
  - mapped `M_hat`
  - final hybrid dict
  - exported tensor view
- Lambda differentiation is real in the live first-step path.
- The earlier Stage 1 stop result should therefore be treated as invalid for method judgment.

The correct next action is:

- rerun the three-case Stage 1 hybrid evaluation cleanly from the fixed runtime and regenerate the tracked Stage 1 artifacts.
