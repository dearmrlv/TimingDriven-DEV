# DCF First Implementation

This note records the first working DCF integration and the initial regression checks.

## Summary

- DCF is implemented as a new timing weighting scheme: `net_weighting_scheme: "dcf"`
- Standard STA remains unchanged; DCF runs as an extra reverse pass after STA
- All timing arcs participate in propagation
- Only physical net arcs are exported to the placer
- The placer still consumes weights through the existing pin-to-pin attraction path
- Existing DREAMPlace 4.0 and Efficient-TDP configs remain unchanged and still run cleanly

### Current DCF Results

| case | DREAMPlace 4.0 TNS | DREAMPlace 4.0 WNS | DREAMPlace 4.0 HPWL | DREAMPlace 4.0 runtime | Efficient-TDP TNS | Efficient-TDP WNS | Efficient-TDP HPWL | Efficient-TDP runtime | DCF v1 TNS | DCF v1 WNS | DCF v1 HPWL | DCF v1 runtime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| superblue1 | -86.205780 | -14.138051 | 5.764892E+09 | 402.854 | -15.665889 | -8.323147 | 4.188897E+08 | 542.367 | -48.398495 | -23.075512 | 4.448847E+08 | 317.407 |
| superblue16 | -64.993815 | -14.681975 | 1.677648E+09 | 292.204 | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 | -99.327000 | -23.684324 | 4.887341E+08 | 231.157 |
| superblue18 | -47.919910 | -11.780133 | 2.065470E+09 | 244.688 | -16.047550 | -7.073299 | 2.338333E+08 | 262.014 | -17.725619 | -7.188731 | 2.373461E+08 | 226.864 |

All DCF runs above completed without crash or NaN.

## Scope

DCF was added as a new timing weighting scheme inside the existing timing-to-weight pipeline. The global placement loop, the quadratic pin-to-pin attraction objective, and the existing DREAMPlace 4.0 / Efficient-TDP baselines were left intact.

## Code Changes

- `dreamplace/params.json`
  - added default-off DCF parameters: `enable_dcf`, `dcf_tau_A`, `dcf_tau_S`, `dcf_momentum`, `dcf_bin_edges`
- `dreamplace/BasicPlace.py`
  - passed DCF parameters into `TimingOpt`
  - sized the pair buffer from the pin count so DCF can export more net arcs safely
- `dreamplace/NonLinearPlace.py`
  - passed the current placement positions into `timing_op.update_net_weights(...)`
- `dreamplace/ops/timing/timing.py`
  - added scheme dispatch for `net_weighting_scheme: "dcf"`
  - converted user-facing deficit bins from ps into the raw timer unit
  - forwarded DCF parameters, pin geometry, and current positions into the C++ timing update path
- `dreamplace/ops/timing/src/timing_cpp.h`
- `dreamplace/ops/timing/src/timing_cpp.cpp`
  - extended the timing-weight update interface to carry the current positions, pin geometry, and DCF parameters
- `dreamplace/ops/timing/src/net_weighting_scheme.h`
  - added `NetWeightingScheme::DCF`
  - implemented the first DCF pass
  - exported DCF-derived net-arc weights into the existing `pin2pin_net_weight` dictionary
- `thirdparty/OpenTimer/ot/timer/pin.hpp`
  - added read-only `fanins()` and `fanouts()` accessors
- `thirdparty/OpenTimer/ot/timer/arc.hpp`
  - added read-only evaluated arc-delay accessor
- `thirdparty/OpenTimer/ot/timer/timer.hpp`
- `thirdparty/OpenTimer/ot/timer/timer.cpp`
  - added a read-only helper to enumerate negative endpoints for a given timing split
- `test/iccad2015.dcf/`
  - added first-pass DCF configs for `superblue18`, `superblue16`, and `superblue1`

## Implemented DCF Variant

- Arc coverage: all timing arcs participate in reverse propagation
- Export coverage: only physical net arcs are exported to the placer
- Distribution form: fixed 4-bin deficit histogram
  - bins in ps: `[0, 20)`, `[20, 50)`, `[50, 150)`, `[150, +inf)`
- Endpoint injection:
  - `delta_t = max(0, -slack(t))`
  - one-hot injection into the matching deficit bin
- Propagation:
  - standard STA still runs first
  - DCF runs as an additional reverse pass after STA
  - current implementation uses setup / `Split::MAX`
  - state is tracked on `(pin, rise/fall)` timing states and accumulated onto physical arcs
- Placer consumption:
  - `U = S + 0.5 * T`
  - `U_tilde = U * eta`, with `eta` = current Manhattan pin-pair length
  - final pair weight = `log(1 + U_tilde)` with EMA smoothing by `dcf_momentum`
  - weights flow through the existing pin-to-pin attraction path unchanged

## superblue18 Check

### Baseline compatibility

- DREAMPlace 4.0 config still runs cleanly:
  - `test/iccad2015.ot/superblue18.json`
  - final: `HPWL 2.065470E+09`, `TNS -47.919910`, `WNS -11.780133`, `NVP 12595`
- Efficient-TDP config still runs cleanly:
  - `test/iccad2015.pin2pin/superblue18.json`
  - final: `HPWL 2.338333E+08`, `TNS -16.047550`, `WNS -7.073299`, `NVP 11563`

### DCF run

- Config: `test/iccad2015.dcf/superblue18.json`
- End-to-end execution: passed without crash or NaN
- Final metrics:
  - `HPWL 2.373461E+08`
  - `TNS -17.725619`
  - `WNS -7.188731`
  - `NVP 11706`

### DCF log sanity

- First DCF update on `superblue18`:
  - failing endpoints: `5048`
  - exported pin pairs: `114241`
  - total exported weight mass: `563457.9375`
  - DCF pass runtime: `1.839 s`
- Later updates remained nontrivial:
  - exported pin pairs stayed around `51k` to `66k`
  - total exported weight mass stayed around `235k` to `294k`
  - DCF pass runtime stayed around `1.6 s` to `1.7 s`
- Whole timing-weight update step on `superblue18` stayed around `3.2 s` to `3.5 s`

## Follow-up DCF Checks

### superblue16

- Config: `test/iccad2015.dcf/superblue16.json`
- End-to-end execution: passed without crash or NaN
- Final metrics:
  - `HPWL 4.887341E+08`
  - `TNS -99.327000`
  - `WNS -23.684324`
  - `NVP 28919`
- DCF behavior:
  - exported pin pairs ranged from about `179k` to `401k`
  - total exported weight mass ranged from about `9.93e5` to `2.78e6`
  - DCF pass runtime stayed around `2.4 s` to `3.2 s`
  - whole timing-weight update step stayed around `4.5 s` to `5.2 s`

### superblue1

- Config: `test/iccad2015.dcf/superblue1.json`
- End-to-end execution: passed without crash or NaN
- Final metrics:
  - `HPWL 4.448847E+08`
  - `TNS -48.398495`
  - `WNS -23.075512`
  - `NVP 22028`
- DCF behavior:
  - exported pin pairs ranged from about `97k` to `167k`
  - total exported weight mass ranged from about `5.79e5` to `1.37e6`
  - DCF pass runtime stayed around `2.6 s` to `3.0 s`
  - whole timing-weight update step stayed around `5.2 s` to `5.6 s`

## Assessment

- DCF propagation behaved as expected for a first version:
  - the pass executed on every timing update
  - many arcs accumulated nonzero mass
  - exported pin-pairs were nontrivial on all tested cases
  - weights were neither all-zero nor exploding
  - placement remained stable through legalization and final STA
- Signal shape:
  - not degenerate and not pathologically concentrated
  - still fairly broad on larger cases, especially `superblue16`
  - top weights stayed in a readable low-30 range while a large tail of pairs remained active
- Runtime overhead:
  - acceptable for a first inspectable implementation
  - noticeably heavier than the smallest path-based update, but still modest relative to full placement runtime

## Next Adjustment

The first tuning target should be attribution sharpness, not objective redesign.

- Recommended next step:
  - decrease `dcf_tau_A` and/or `dcf_tau_S` to reduce diffuseness before adding any export pruning
- If that is still too broad:
  - add a lightweight export filter on low-utility net arcs, while keeping all-arc propagation unchanged
