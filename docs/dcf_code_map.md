# DCF Code Map

This note maps the first DCF implementation onto the current codebase without changing the overall placer structure.

## A. Timing analysis and feedback

- Timer construction and initial STA: `dreamplace/Placer.py`
  - `place`: builds `Timer.Timer()`, reads timing constraints, then calls `timer.update_timing()` before placement starts.
- Timing operator construction: `dreamplace/BasicPlace.py`
  - `build_timing_op`: builds `timing.TimingOpt` and passes timing DB handles, pin geometry, net weights, and the shared `placedb.pin2pin_net_weight` dictionary.
- Timing update cadence in global placement: `dreamplace/NonLinearPlace.py`
  - inside the main optimization loop, every 15 iterations after `start_iter`:
    1. `timing_op(pos_cpu)` updates RC trees for the current placement
    2. `timing_op.timer.update_timing()` runs standard STA
    3. `timing_op.update_net_weights(...)` runs the selected timing-to-weight scheme
- Python scheme dispatch: `dreamplace/ops/timing/timing.py`
  - `TimingOpt.update_net_weights` maps the JSON string `net_weighting_scheme` to the C++ enum code.
- C++ scheme dispatch: `dreamplace/ops/timing/src/timing_cpp.cpp`
  - `updateNetWeightCppLauncher` selects the concrete specialization in `net_weighting_scheme.h`.
- Existing timing-weight implementations: `dreamplace/ops/timing/src/net_weighting_scheme.h`
  - `LILITH` updates scalar net weights.
  - `PIN2PIN` extracts path-derived pin pairs and updates `pin2pin_net_weight`.

## B. Placement consumption path

- Shared pin-pair storage: `dreamplace/PlaceDB.py`
  - `self.pin2pin_net_weight = {}` is the persistent timing-to-pair handoff object.
  - `self.length = [0]` stores the active pair count for the CUDA path.
- Device-side pair tensors: `dreamplace/BasicPlace.py`
  - `PlaceDataCollection` allocates `pairs` and `weights` tensors used by the CUDA pin-to-pin attraction op.
- Dict to tensor transfer: `dreamplace/NonLinearPlace.py`
  - after each timing-weight update, the contents of `placedb.pin2pin_net_weight` are flattened into `data_collections.pairs`, `data_collections.weights`, and `placedb.length[0]`.
- Objective consumption: `dreamplace/PlaceObj.py`
  - `build_pin2pin_net_weight` builds `pin2pin_attraction.Pin2PinAttraction`.
  - `obj_fn` adds the existing quadratic pin-to-pin attraction loss when `params.pin2pin_net_weighting` is enabled.
- Pair-loss implementation:
  - Python wrapper: `dreamplace/ops/pin2pin_attraction/pin2pin_attraction.py`
  - CPU kernel: `dreamplace/ops/pin2pin_attraction/src/pin2pin_attraction.cpp`
  - CUDA kernel: `dreamplace/ops/pin2pin_attraction/src/pin2pin_attraction_cuda.cpp`

## C. DCF extension points

- Config fields: `dreamplace/params.json`
  - add `enable_dcf`, `dcf_tau_A`, `dcf_tau_S`, `dcf_momentum`, and `dcf_bin_edges`.
- Timing operator plumbing:
  - `dreamplace/BasicPlace.py`
  - `dreamplace/ops/timing/timing.py`
  - `dreamplace/ops/timing/src/timing_cpp.h`
  - `dreamplace/ops/timing/src/timing_cpp.cpp`
- Main DCF implementation point:
  - `dreamplace/ops/timing/src/net_weighting_scheme.h`
  - DCF is added as a new timing weighting scheme, not a new placer pipeline.
- Read-only timing graph access for DCF:
  - `thirdparty/OpenTimer/ot/timer/pin.hpp`
  - `thirdparty/OpenTimer/ot/timer/arc.hpp`
  - `thirdparty/OpenTimer/ot/timer/timer.hpp`
  - `thirdparty/OpenTimer/ot/timer/timer.cpp`
  - These are the minimal accessor additions needed to enumerate failing endpoints, traverse predecessor arcs, and read evaluated arc delays without changing STA itself.
- Lightweight DCF logging:
  - best added in `dreamplace/ops/timing/src/net_weighting_scheme.h` with `dreamplacePrint(...)` so each timing-weight update logs DCF-specific counters and runtime close to the implementation.

## Mapping To The Three Conceptual Parts

### (1) Which arcs get DCF

- DCF state is computed on all OpenTimer timing arcs in `dreamplace/ops/timing/src/net_weighting_scheme.h`.
- Export to the placer is filtered to physical net arcs only via `arc.is_net_arc()`.
- This keeps cell arcs in the reverse propagation path while preserving the existing pin-to-pin attraction consumer.

### (2) Distribution representation and propagation

- Node temporary state: a 4-bin bad-mass histogram `Q_v[4]` on timing graph states.
- Arc state: a 4-bin histogram `H_a[4]` on each timing arc.
- Failing endpoint injection uses endpoint slack from OpenTimer after normal STA.
- Reverse propagation uses predecessor arcs, arrival times, required times, and evaluated arc delays from OpenTimer.
- The DCF reverse pass is implemented after standard STA inside the timing weighting update, not inside the global placement loop itself.

### (3) Placer consumption

- DCF does not change the placement objective shape.
- DCF converts arc histograms on physical net arcs into pin-pair weights and writes them into `placedb.pin2pin_net_weight`.
- The existing `NonLinearPlace -> pairs/weights tensors -> Pin2PinAttraction -> quadratic loss` path remains the primary consumer.
