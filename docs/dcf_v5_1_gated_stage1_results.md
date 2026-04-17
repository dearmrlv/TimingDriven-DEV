# DCF v5.1 Gated Hybrid Stage 1 Results

This note records the narrow Stage 1 check for the gated DCF v5.1 hybrid on branch `exp/dcf-v5.1-gated-hybrid`.

Scope:

- cases:
  - `superblue16`
  - `superblue3`
  - `superblue18`
- comparison methods:
  - Efficient-TDP baseline from `README.research.md`
  - ungated `dcf_v5_hybrid_l010`
  - gated `dcf_v5_1_gated_g010`
  - gated `dcf_v5_1_gated_g025`
  - gated `dcf_v5_1_gated_g050`
- output tag:
  - `dcf_v5_1_gated_stage1`

No propagation change was made.
No bin change was made.
No reverse-attribution change was made.
No objective change was made.
No tail-term change was made.
No full-suite run was made.

## Tracked Artifacts

- `docs/artifacts/dcf_v5_1_gated_stage1_metrics.csv`
- `docs/artifacts/dcf_v5_1_gated_stage1_engagement_sanity.csv`
- `docs/artifacts/dcf_v5_1_gated_superblue16_trajectory.csv`

## Did The Gated Hybrid Engage Correctly?

Yes.

The first-step engagement sanity table shows that all three gated variants are active on all three cases:

- `superblue16`
  - base pair count `101818`
  - gated pair counts `10182`, `25455`, `50909`
  - exported total mass rises from `1034690.5625` to `1034705.25`
- `superblue3`
  - base pair count `44353`
  - gated pair counts `4436`, `11089`, `22177`
  - exported total mass rises from `455126.46875` to `455153.28125`
- `superblue18`
  - base pair count `25805`
  - gated pair counts `2581`, `6452`, `12903`
  - exported total mass rises from `268902.0` to `268922.75`

So the gated path is engaged, the gate is active, and the gate fractions do change exported first-step behavior.

## Stage 1 Table

| case | method | lambda | gate | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| superblue16 | Efficient-TDP | - | - | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 |
| superblue16 | DCF v5 hybrid | 0.10 | - | -17.338564 | -17.313271 | 4.639473E+08 | 525.121 |
| superblue16 | DCF v5.1 gated hybrid | 0.10 | 0.10 | -17.587287 | -12.363670 | 4.638116E+08 | 481.075 |
| superblue16 | DCF v5.1 gated hybrid | 0.10 | 0.25 | -17.471917 | -8.021292 | 4.638096E+08 | 462.813 |
| superblue16 | DCF v5.1 gated hybrid | 0.10 | 0.50 | -18.224451 | -17.238732 | 4.640592E+08 | 460.028 |
| superblue3 | Efficient-TDP | - | - | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | DCF v5 hybrid | 0.10 | - | -21.075265 | -11.855161 | 4.626795E+08 | 1010.867 |
| superblue3 | DCF v5.1 gated hybrid | 0.10 | 0.10 | -20.260102 | -11.936544 | 4.626648E+08 | 635.101 |
| superblue3 | DCF v5.1 gated hybrid | 0.10 | 0.25 | -20.037340 | -11.846602 | 4.626031E+08 | 621.511 |
| superblue3 | DCF v5.1 gated hybrid | 0.10 | 0.50 | -20.494532 | -11.951053 | 4.626844E+08 | 629.027 |
| superblue18 | Efficient-TDP | - | - | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 |
| superblue18 | DCF v5 hybrid | 0.10 | - | -15.927817 | -7.079268 | 2.337608E+08 | 436.093 |
| superblue18 | DCF v5.1 gated hybrid | 0.10 | 0.10 | -15.976050 | -7.015169 | 2.338743E+08 | 302.443 |
| superblue18 | DCF v5.1 gated hybrid | 0.10 | 0.25 | -15.882309 | -7.015556 | 2.338012E+08 | 303.019 |
| superblue18 | DCF v5.1 gated hybrid | 0.10 | 0.50 | -15.781382 | -6.989462 | 2.344943E+08 | 302.970 |

## Case Reading

### superblue16

Gating helps materially.

- ungated WNS: `-17.313271`
- gated `0.10` WNS: `-12.363670`
- gated `0.25` WNS: `-8.021292`
- gated `0.50` WNS: `-17.238732`

So the gate clearly matters here.

`0.25` is the best setting on this case:

- it nearly recovers Efficient-TDP WNS sharpness
- it improves WNS by about `9.29` over the ungated hybrid
- it stays very close to the ungated TNS and HPWL range

This is the strongest evidence in the whole Stage 1 that selective augmentation is the right direction.

### superblue3

Gating keeps the hybrid near parity and improves over the ungated v5.0 result.

- ungated TNS/WNS: `-21.075265 / -11.855161`
- gated `0.25`: `-20.037340 / -11.846602`

`0.25` is also the best setting here overall:

- best TNS among the gated settings
- best WNS among the gated settings
- best HPWL among the gated settings

It still does not beat Efficient-TDP, but it stays close and clearly avoids regression relative to the ungated hybrid.

### superblue18

Gating preserves most of the good behavior, but does not produce a clean win over Efficient-TDP.

- ungated TNS/WNS: `-15.927817 / -7.079268`
- gated `0.10`: `-15.976050 / -7.015169`
- gated `0.25`: `-15.882309 / -7.015556`
- gated `0.50`: `-15.781382 / -6.989462`

So gating helps relative to the ungated hybrid on WNS and runtime.

The best tradeoff here is split:

- `0.25` gives the best HPWL and strong TNS
- `0.50` gives the best TNS and the best WNS among the gated settings

But none of the gated settings cleanly beats Efficient-TDP on both TNS and WNS together.

## Answers

### 1. Did the gated hybrid engage correctly?

Yes.

The first-step sanity table confirms:

- nonzero base pin2pin pairs
- nonzero gated pair counts
- correct gate fractions near `10% / 25% / 50%`
- nonzero mapped `M_hat` pairs
- nonzero final and exported pair counts
- different exported first-step masses across gate settings

### 2. Which gate fraction looks best?

`0.25` looks best overall.

Reasons:

- it is the clear best setting on `superblue16`
- it is also the best setting on `superblue3`
- it remains competitive on `superblue18`
- it improves strongly over the ungated hybrid without the instability seen at `0.50`

### 3. Does gating improve `superblue16` enough to justify continuing?

Yes, for continuing the direction.

No, for declaring success.

Why:

- `0.25` recovers WNS from `-17.313271` to `-8.021292`
- that is a large improvement and lands very close to Efficient-TDP `-7.841117`
- but it still does not beat Efficient-TDP on either TNS or WNS

So the gating hypothesis is validated, but the method is not yet baseline-winning.

### 4. Does gating preserve or damage the gains on `superblue3` and `superblue18`?

It mostly preserves them and improves over the ungated hybrid.

- `superblue3`: yes, especially at `0.25`
- `superblue18`: yes relative to ungated v5.0, but the best gated results are still only near-baseline rather than decisive wins

### 5. Is the evidence strong enough now to justify a full-suite run?

Not yet.

This Stage 1 is meaningfully stronger than ungated v5.0, but still not strong enough for a confident full-suite spend:

- `superblue16` is much better, but still not a baseline beat
- `superblue3` is close, but still not a baseline beat
- `superblue18` is preserved reasonably well, but still not a clean win

So the gated direction is worth keeping alive, but it has not yet earned Stage 2.

## Conservative Conclusion

- The gated hybrid engaged correctly.
- The gate is real and auditable.
- Restricting DCF `M` augmentation does help preserve Efficient-TDP sharpness.
- The best current setting is `gate_fraction = 0.25` with `lambda = 0.10`.
- The main hypothesis is supported on `superblue16`: selective augmentation is much better than ungated augmentation.
- Even so, the method is still not strong enough to justify a full-suite run yet.
