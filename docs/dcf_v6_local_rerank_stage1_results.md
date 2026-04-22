# DCF v6 Local Rerank Stage 1 Results

This note records the first narrow Stage 1 check for the DCF v6 local-rerank hypothesis on branch `exp/dcf-v6-local-rerank`.

Scope:

- rerank windows:
  - `5%`
  - `10%`
  - `20%`
- fixed rerank strength:
  - `alpha = 0.20`
- cases:
  - `superblue16`
  - `superblue3`
  - `superblue18`
- comparisons:
  - Efficient-TDP baseline from `README.research.md`
  - previous gated-hybrid best reference: `gate=0.25`, `lambda=0.04`
  - DCF v6 local rerank at `5% / 10% / 20%`

No propagation change was made.
No bin change was made.
No reverse-attribution change was made.
No objective change was made.
No full-suite run was made.

## Tracked Artifacts

- `docs/artifacts/dcf_v6_local_rerank_stage1_metrics.csv`
- `docs/artifacts/dcf_v6_local_rerank_stage1_engagement_sanity.csv`
- `docs/artifacts/dcf_v6_local_rerank_superblue16_trajectory.csv`

## Did The Local Rerank Path Engage Correctly?

Yes.

The first-step sanity table confirms all three rerank windows are active on all three cases.

Examples:

- `superblue16`
  - base pair count `101818`
  - rerank window sizes `5091 / 10182 / 20364`
  - mapped `M_hat` pair count `84056`
  - changed-order pair counts `4559 / 9643 / 19831`
- `superblue3`
  - changed-order pair counts `992 / 3187 / 7616`
- `superblue18`
  - changed-order pair counts `689 / 1847 / 4430`

So the rerank window is real, DCF `M` is aligned, and local order inside the selected prefix is changing.

## Stage 1 Table

| case | method | rerank window | alpha | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| superblue16 | Efficient-TDP | - | - | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 |
| superblue16 | DCF v5.2 gated hybrid | - | 0.20 | -22.155895 | -7.803605 | 4.726714E+08 | 448.225 |
| superblue16 | DCF v6 local rerank | 0.05 | 0.20 | -17.375241 | -10.539357 | 4.638693E+08 | 478.431 |
| superblue16 | DCF v6 local rerank | 0.10 | 0.20 | -17.914635 | -7.874568 | 4.639684E+08 | 481.300 |
| superblue16 | DCF v6 local rerank | 0.20 | 0.20 | -24.018270 | -7.983444 | 4.738115E+08 | 395.255 |
| superblue3 | Efficient-TDP | - | - | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | DCF v5.2 gated hybrid | - | 0.20 | -21.007280 | -11.909313 | 4.627091E+08 | 774.882 |
| superblue3 | DCF v6 local rerank | 0.05 | 0.20 | -20.807077 | -11.981086 | 4.627228E+08 | 682.528 |
| superblue3 | DCF v6 local rerank | 0.10 | 0.20 | -20.553830 | -11.854659 | 4.625727E+08 | 686.090 |
| superblue3 | DCF v6 local rerank | 0.20 | 0.20 | -21.592112 | -11.951284 | 4.626012E+08 | 699.063 |
| superblue18 | Efficient-TDP | - | - | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 |
| superblue18 | DCF v5.2 gated hybrid | - | 0.20 | -16.005418 | -6.876197 | 2.346284E+08 | 299.179 |
| superblue18 | DCF v6 local rerank | 0.05 | 0.20 | -16.689635 | -7.226962 | 2.342712E+08 | 324.633 |
| superblue18 | DCF v6 local rerank | 0.10 | 0.20 | -16.825475 | -6.941335 | 2.344257E+08 | 327.242 |
| superblue18 | DCF v6 local rerank | 0.20 | 0.20 | -16.108066 | -7.008085 | 2.339016E+08 | 344.881 |

## Reading The Line

### superblue16

This is the deciding case, and the v6 line does not clearly improve on the previous gated reference.

Compared to the previous gated best:

- previous gated best:
  - `TNS -22.155895`
  - `WNS -7.803605`
  - `HPWL 4.726714E+08`
- rerank `0.05`:
  - WNS degrades badly to `-10.539357`
- rerank `0.10`:
  - WNS stays close at `-7.874568`
  - but TNS degrades sharply to `-17.914635`
- rerank `0.20`:
  - TNS is the strongest rerank value at `-24.018270`
  - but WNS and HPWL are both slightly worse than the previous gated reference

So the local-rerank line does not deliver a clearly better `superblue16` balance than the gated-hybrid best reference.

### superblue3

The `10%` window is the best rerank setting on this case.

- rerank `0.10` improves on the previous gated reference in TNS, WNS, and HPWL
- but it still does not beat Efficient-TDP

This case is encouraging for the local-rerank idea, but not decisive.

### superblue18

This case does not favor the local-rerank line.

- all rerank windows lose ground to the previous gated reference on WNS
- `20%` gets closest on HPWL, but not enough to compensate

So the local rerank is not clearly safer or stronger here.

## Answers

### 1. Did the local rerank path engage correctly?

Yes.

The sanity table shows nonzero rerank windows, nonzero mapped `M_hat`, and large numbers of pairs with changed local order inside the selected prefix.

### 2. Which rerank window looks best?

`10%` looks best overall.

Reason:

- it is the best rerank setting on `superblue3`
- it is the least damaging rerank setting on `superblue16`
- it is still weaker than the gated reference overall, but among the rerank variants it is the best tradeoff

### 3. Does this line improve on the previous gated-hybrid best reference?

No.

The clearest blocker is `superblue16`:

- none of the rerank windows gives a better combined TNS/WNS/HPWL balance than the previous gated reference

The line helps somewhat on `superblue3`, but that is not enough to outweigh the weaker `superblue16` and `superblue18` outcomes.

### 4. On `superblue16`, is WNS preserved better than before?

No, not in a clearly useful way.

- `10%` keeps WNS close to the previous gated reference
- but it gives back far too much TNS
- `20%` helps TNS but slightly worsens WNS and HPWL relative to the previous gated reference

So the local-rerank line does not preserve Efficient-TDP sharpness better in a practically better overall way on the blocker case.

### 5. Is this line promising enough to continue, or should it also be deprioritized?

It should also be deprioritized.

The line is technically valid and interpretable, but the three-case Stage 1 result does not show it to be clearly more promising than the previous gated-hybrid line.

## Conservative Conclusion

- The v6 local-rerank path is alive and auditable.
- The local window and changed-order signal are real.
- But the first Stage 1 result does not improve on the previous gated-hybrid best reference.
- `10%` is the best rerank window among the v6 candidates, but it is still not strong enough to promote.
- This line should be deprioritized alongside the gated-hybrid line rather than pushed to broader evaluation.
