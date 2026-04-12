# Baseline Reproduction Notes

This document maps the repository for baseline reproduction work only. It does not propose or implement any algorithmic changes.

## Repository map

| Path | Role in baseline reproduction |
| --- | --- |
| `CMakeLists.txt` | Top-level native build entrypoint. Configures CUDA, PyTorch extensions, install prefix, and subdirectories. |
| `cmake/TorchExtension.cmake` | Finds the active Python and PyTorch install, then builds the C++/CUDA extensions against that environment. |
| `dreamplace/Placer.py` | Main runtime CLI entrypoint for placement runs. |
| `dreamplace/BasicPlace.py` | Builds placement operators, including timing feedback support. |
| `dreamplace/NonLinearPlace.py` | Main optimization flow and in-run metric logging. |
| `dreamplace/PlaceObj.py` | Placement objective assembly. Efficient-TDP adds the pin-to-pin attraction term here. |
| `dreamplace/ops/timing/src/net_weighting_scheme.h` | Timing-driven net-weight update implementations. Contains both `lilith` and `pin2pin` paths. |
| `dreamplace/params.json` | Parameter schema and defaults, including `result_dir`. |
| `test/iccad2015.ot/*.json` | DREAMPlace 4.0 timing-driven baseline configs using `net_weighting_scheme: "lilith"`. |
| `test/iccad2015.pin2pin/*.json` | Efficient-TDP baseline configs using `net_weighting_scheme: "pin2pin"`. |
| `benchmarks/iccad2015.ot/` | Local external ICCAD2015 benchmark payload. It is intentionally kept out of git. |
| `install/run.sh` | Existing convenience wrapper. It currently defaults to the Efficient-TDP path and only runs `superblue18`. |

## Main build path

1. `cmake -S . -B build`
2. `cmake --build build`
3. `cmake --install build`

The install tree under `install/` is the native runtime location for the compiled Python extensions and copied configs.

## Main run entrypoints

- Native CLI: `python dreamplace/Placer.py <config.json>`
- Installed runtime location: `install/dreamplace/Placer.py`
- Baseline config families:
  - DREAMPlace 4.0: `install/test/iccad2015.ot/<case>.json`
  - Efficient-TDP: `install/test/iccad2015.pin2pin/<case>.json`

## Canonical Remotes

- `origin`: `git@github.com:dearmrlv/TimingDriven-DEV.git`
- `ustc`: `git@git.lug.ustc.edu.cn:lvzhengyang/timingdriven-dev.git`
- `upstream`: `https://github.com/lamda-bbo/Efficient-TDP.git`

Push branch work to `origin` and `ustc`. Treat `upstream` as the original source repository, not the default push target.

## Benchmark and config locations

- Source benchmark configs live under `test/`
- Installed benchmark configs live under `install/test/`
- Benchmark payload is expected at `benchmarks/iccad2015.ot/`
- The original README asks users to place benchmarks under `install/benchmarks/iccad2015.ot`, which conflicts with the repo-root single-case invocation. The reproduction scripts resolve this by creating a symlink from `install/benchmarks/iccad2015.ot` back to the local external benchmark directory.

## Baseline implementation split

### DREAMPlace 4.0

- Config path: `test/iccad2015.ot/*.json`
- Distinguishing config setting: `net_weighting_scheme: "lilith"`
- Matching code path:
  - `dreamplace/ops/timing/src/net_weighting_scheme.h` (`LILITH` specialization)
  - `dreamplace/ops/timing/timing.py` (`"lilith"` scheme selection)

### Efficient-TDP

- Config path: `test/iccad2015.pin2pin/*.json`
- Distinguishing config settings:
  - `net_weighting_scheme: "pin2pin"`
  - `pin2pin_net_weighting: 1`
- Matching code path:
  - `dreamplace/ops/timing/src/net_weighting_scheme.h` (`PIN2PIN` specialization)
  - `dreamplace/PlaceObj.py` (pin-to-pin attraction term)

## Evaluation path

- Native in-run metrics come from the placer log:
  - HPWL from `EvalMetrics`
  - TNS/WNS from OpenTimer after timing feedback and legalization
- The repository does not preserve the official ICCAD2015 evaluation kit.
- The repo README points to an external Google Drive link for that kit.
- For this reproduction pass, `scripts/run_eval.sh` extracts native metrics from the run logs and records the gap to the external official evaluator.

## Final placement artifacts

Each successful run writes the final global placement output under:

- `results/baselines/dreamplace4/<case>/<case>.gp.def`
- `results/baselines/efficient_tdp/<case>/<case>.gp.def`

Additional per-run metadata saved by the reproduction scripts:

- `command.txt`
- `config.json`
- `git_commit.txt`
- `metrics.json`
- log file under `logs/<method>/<case>.log`

## Smoke-test cases

- `superblue1`
- `superblue16`
- `superblue18`

## Parallelism decision

- Placement runs are kept sequential on this machine.
- Reason: there is one visible GPU (`RTX 4060 Ti`, `16380 MiB`), and each ICCAD2015 run is a long single-GPU job with large CUDA tensors and timing analysis work. Running multiple placement jobs concurrently on the same GPU would mainly add contention and memory pressure rather than improving throughput.
- Lightweight tasks such as log parsing and file reads can still be parallelized.

## Smoke-test summary

| case | method | TNS | WNS | HPWL | runtime | status | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| superblue1 | DREAMPlace 4.0 | -86.205780 | -14.138051 | 5.764892E+09 | 402.854 | ok | native OpenTimer metrics |
| superblue1 | Efficient-TDP | -15.665889 | -8.323147 | 4.188897E+08 | 542.367 | ok | native OpenTimer metrics |
| superblue16 | DREAMPlace 4.0 | -64.993815 | -14.681975 | 1.677648E+09 | 292.204 | ok | native OpenTimer metrics |
| superblue16 | Efficient-TDP | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 | ok | native OpenTimer metrics |
| superblue18 | DREAMPlace 4.0 | -47.919910 | -11.780133 | 2.065470E+09 | 244.688 | ok | native OpenTimer metrics |
| superblue18 | Efficient-TDP | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 | ok | native OpenTimer metrics |

## Full ICCAD2015 suite template

| case | method | TNS | WNS | HPWL | runtime | status | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| superblue1 | DREAMPlace 4.0 | -86.205780 | -14.138051 | 5.764892E+09 | 402.854 | ok | native OpenTimer metrics |
| superblue1 | Efficient-TDP | -15.665889 | -8.323147 | 4.188897E+08 | 542.367 | ok | native OpenTimer metrics |
| superblue3 | DREAMPlace 4.0 | -50.278965 | -15.729451 | 1.619536E+09 | 502.761 | ok | native OpenTimer metrics |
| superblue3 | Efficient-TDP | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 | ok | native OpenTimer metrics |
| superblue4 | DREAMPlace 4.0 | -153.626060 | -13.704465 | 1.786124E+09 | 241.609 | ok | native OpenTimer metrics |
| superblue4 | Efficient-TDP | -90.259830 | -9.161039 | 3.180224E+08 | 1324.106 | ok | native OpenTimer metrics |
| superblue5 | DREAMPlace 4.0 | -101.250460 | -27.685633 | 2.608756E+09 | 454.780 | ok | native OpenTimer metrics |
| superblue5 | Efficient-TDP | -65.440080 | -24.220008 | 4.852562E+08 | 748.797 | ok | native OpenTimer metrics |
| superblue7 | DREAMPlace 4.0 | -61.622710 | -15.395518 | 8.582195E+08 | 597.971 | ok | native OpenTimer metrics |
| superblue7 | Efficient-TDP | -37.190520 | -15.395518 | 5.980916E+08 | 757.736 | ok | native OpenTimer metrics |
| superblue10 | DREAMPlace 4.0 | -660.061080 | -23.671605 | 6.766032E+09 | 759.398 | ok | native OpenTimer metrics |
| superblue10 | Efficient-TDP | -564.221600 | -23.441709 | 9.145873E+08 | 1866.491 | ok | native OpenTimer metrics |
| superblue16 | DREAMPlace 4.0 | -64.993815 | -14.681975 | 1.677648E+09 | 292.204 | ok | native OpenTimer metrics |
| superblue16 | Efficient-TDP | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 | ok | native OpenTimer metrics |
| superblue18 | DREAMPlace 4.0 | -47.919910 | -11.780133 | 2.065470E+09 | 244.688 | ok | native OpenTimer metrics |
| superblue18 | Efficient-TDP | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 | ok | native OpenTimer metrics |

## Risks and unclear points

- The repository does not vendor the ICCAD2015 benchmark payload or the official evaluation kit.
- The repository default scripts point to Efficient-TDP, not DREAMPlace 4.0.
- The machine-local benchmark payload is intentionally external data, currently linked into the repo.
- GPU execution is required for baseline runs. If CUDA-enabled PyTorch wheels or CUDA extension builds fail, the run should stop instead of silently falling back to CPU.
- The native reported TNS/WNS come from OpenTimer inside the repository, not the official ICCAD2015 evaluator.
