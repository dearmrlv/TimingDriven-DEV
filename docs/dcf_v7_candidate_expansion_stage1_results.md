# DCF v7 Candidate Expansion Stage 1 Results

This note records the first narrow Stage 1 check for the DCF v7 candidate-expansion hypothesis on branch `exp/dcf-v7-candidate-expansion`.

Scope:

- supplementary expansion sizes:
  - `+1%`
  - `+2%`
  - `+5%`
- cases:
  - `superblue16`
  - `superblue3`
  - `superblue18`
- comparisons:
  - Efficient-TDP baseline from `README.research.md`
  - previous gated-hybrid best reference: `gate=0.25`, `lambda=0.04`
  - DCF v7 candidate expansion at `+1% / +2% / +5%`

No propagation change was made.
No bin change was made.
No reverse-attribution change was made.
No objective change was made.
No base pair weight was modified.
No full-suite run was made.

## Tracked Artifacts

- `docs/artifacts/dcf_v7_candidate_expansion_stage1_metrics.csv`
- `docs/artifacts/dcf_v7_candidate_expansion_stage1_engagement_sanity.csv`
- `docs/artifacts/dcf_v7_candidate_expansion_superblue16_trajectory.csv`

## Did The Candidate-Expansion Path Engage Correctly?

Yes.

The first-step sanity table shows:

- the base pair set is intact
- supplementary pairs are actually added
- all supplementary pairs receive nonzero weight
- supplementary mass is much smaller than base mass

Examples:

- `superblue16`
  - base pair count `101818`
  - supplementary counts `1019 / 2037 / 5091`
  - base mass about `1.034e6`
  - supplementary mass `1.019e4 / 2.037e4 / 5.091e4`
- `superblue3`
  - supplementary counts `444 / 888 / 2218`
- `superblue18`
  - supplementary counts `259 / 517 / 1291`

So the path engaged correctly and the expansion stays numerically small relative to the base mass.

## Stage 1 Table

| case | method | expansion | TNS | WNS | HPWL | runtime (s) |
| --- | --- | --- | --- | --- | --- | --- |
| superblue16 | Efficient-TDP | - | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 |
| superblue16 | DCF v5.2 gated hybrid | - | -22.155895 | -7.803605 | 4.726714E+08 | 448.225 |
| superblue16 | DCF v7 candidate expansion | 0.01 | -68.829540 | -9.721957 | 4.900658E+08 | 505.608 |
| superblue16 | DCF v7 candidate expansion | 0.02 | -122.644110 | -13.035047 | 4.880967E+08 | 533.919 |
| superblue16 | DCF v7 candidate expansion | 0.05 | -99.118360 | -14.338023 | 4.939535E+08 | 508.776 |
| superblue3 | Efficient-TDP | - | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 |
| superblue3 | DCF v5.2 gated hybrid | - | -21.007280 | -11.909313 | 4.627091E+08 | 774.882 |
| superblue3 | DCF v7 candidate expansion | 0.01 | -24.445023 | -12.739604 | 4.680733E+08 | 652.111 |
| superblue3 | DCF v7 candidate expansion | 0.02 | -36.772040 | -15.059357 | 4.677037E+08 | 676.105 |
| superblue3 | DCF v7 candidate expansion | 0.05 | -355.534400 | -20.858781 | 4.674134E+08 | 758.283 |
| superblue18 | Efficient-TDP | - | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 |
| superblue18 | DCF v5.2 gated hybrid | - | -16.005418 | -6.876197 | 2.346284E+08 | 299.179 |
| superblue18 | DCF v7 candidate expansion | 0.01 | -17.271440 | -7.571909 | 2.342116E+08 | 339.582 |
| superblue18 | DCF v7 candidate expansion | 0.02 | -16.730291 | -7.060589 | 2.342292E+08 | 322.350 |
| superblue18 | DCF v7 candidate expansion | 0.05 | -18.490461 | -7.202573 | 2.344683E+08 | 325.615 |

## Reading The Line

### superblue16

This is the blocker case, and the candidate-expansion line is clearly worse than both Efficient-TDP and the previous gated reference.

- previous gated best:
  - `TNS -22.155895`
  - `WNS -7.803605`
  - `HPWL 4.726714E+08`
- best v7 expansion here is `+1%`, but it is still much worse:
  - `TNS -68.829540`
  - `WNS -9.721957`
  - `HPWL 4.900658E+08`

So even the smallest supplementary addition disrupts timing materially on the main blocker case.

### superblue3

This case also degrades across all expansion sizes.

- `+1%` is the least damaging setting
- `+5%` collapses badly

No v7 setting beats the previous gated reference here.

### superblue18

This case behaves similarly.

- `+2%` is the least damaging v7 setting
- but it is still worse than the previous gated reference on both TNS and WNS

So the candidate-expansion line does not preserve Efficient-TDP sharpness better than the earlier DCF integration families.

## Answers

### 1. Can candidate expansion help without damaging Efficient-TDP’s sharpness?

No.

Even though the supplementary mass is numerically small, the top-line timing metrics degrade noticeably on all three cases.

### 2. Which expansion size looks best: +1%, +2%, or +5%?

`+1%` is the least damaging overall.

But it is still clearly worse than the previous gated-hybrid best reference.

### 3. Does this line improve on the previous gated-hybrid best reference?

No.

It is worse on the blocker case `superblue16`, and it is not clearly competitive on `superblue3` or `superblue18` either.

### 4. On `superblue16`, can it improve TNS without giving away WNS?

No.

The smallest expansion already degrades both TNS and WNS substantially relative to the previous gated reference.

### 5. Is this line more promising than the previous two DCF integration families?

No.

The line is technically valid and engaged, but the Stage 1 evidence is clearly weaker than the previous gated-hybrid best line and not better than the local-rerank line either.

## Conservative Conclusion

- The v7 candidate-expansion path is alive and auditable.
- The base set remained intact and supplementary pairs were added conservatively.
- But even very small supplementary additions damage timing too much.
- `+1%` is the least damaging setting, but it is still not competitive with the previous gated-hybrid best reference.
- This line should also be deprioritized rather than continued.
