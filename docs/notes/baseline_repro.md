# Baseline Reproduction Status

## Scope

This note tracks only baseline reproduction work for:

- Efficient-TDP
- DREAMPlace 4.0

No algorithmic changes are introduced here.

## DREAMPlace 4.0 evidence in this repository

Evidence that the DREAMPlace 4.0 timing-driven baseline is preserved:

1. `test/iccad2015.ot/README.md` explicitly cites the DREAMPlace 4.0 papers.
2. `test/iccad2015.ot/*.json` uses `net_weighting_scheme: "lilith"`.
3. `dreamplace/ops/timing/src/net_weighting_scheme.h` contains a dedicated `LILITH` implementation.
4. `dreamplace/ops/timing/timing.py` maps `"lilith"` to a separate weighting-scheme code path.

Likely invocation path:

```bash
python dreamplace/Placer.py test/iccad2015.ot/<case>.json
```

Within the scripted reproduction flow, the installed runtime path is:

```bash
install/dreamplace/Placer.py install/test/iccad2015.ot/<case>.json
```

## Efficient-TDP evidence in this repository

Evidence that Efficient-TDP is implemented as an additive extension over the timing-driven DREAMPlace base:

1. `test/iccad2015.pin2pin/*.json` switches to `net_weighting_scheme: "pin2pin"`.
2. `dreamplace/ops/timing/src/net_weighting_scheme.h` contains a dedicated `PIN2PIN` implementation.
3. `dreamplace/PlaceObj.py` adds the pin-to-pin attraction term into the placement objective when enabled.
4. `dreamplace/params.json` defines the `pin2pin_*` parameters.

Likely invocation path:

```bash
python dreamplace/Placer.py test/iccad2015.pin2pin/<case>.json
```

Within the scripted reproduction flow, the installed runtime path is:

```bash
install/dreamplace/Placer.py install/test/iccad2015.pin2pin/<case>.json
```

## Evaluation gap

- The repository logs native OpenTimer-based TNS and WNS.
- The official ICCAD2015 evaluation kit is referenced in the README, but not present in the repository.
- The native reproduction scripts therefore record:
  - TNS/WNS from the run log
  - HPWL from the run log
  - runtime from the run log
- Any official contest-style evaluation remains external until the official kit is supplied locally.

## Current status

- Environment setup: completed with `uv`
- CUDA build: completed for the baseline-required modules
- DREAMPlace 4.0 smoke runs: completed for `superblue1`, `superblue16`, `superblue18`
- Efficient-TDP smoke runs: completed for `superblue1`, `superblue16`, `superblue18`
- Full ICCAD2015 suite: completed for both baselines with native OpenTimer metrics
