#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = REPO_ROOT / "install"


def configure_imports(runtime_root: Path) -> None:
    runtime_root = runtime_root.resolve()
    search_paths = [runtime_root, runtime_root / "dreamplace"]
    for path in search_paths:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def load_json(path: Path) -> dict:
    with path.open() as fin:
        return json.load(fin)


def build_replay_params(
    source_config: dict,
    snapshot_metadata: dict,
    output_dir: Path,
    scheme: str,
) -> dict:
    timing_step_id = int(snapshot_metadata["timing_step_id"])
    source_scheme = snapshot_metadata["scheme_name"]
    replay_tag = f"replay_from_{source_scheme}_step_{timing_step_id:03d}"

    params = dict(source_config)
    params["net_weighting_scheme"] = scheme
    params["enable_dcf"] = 1 if scheme == "dcf" else 0
    params["pin2pin_net_weighting"] = 1
    params["enable_dcf_diagnostics"] = 1
    params["dcf_diag_dump_dir"] = str(output_dir.parent.parent)
    params["dcf_diag_case_tag"] = replay_tag
    params["dcf_diag_scheme_tag"] = scheme
    params["dcf_diag_dump_step_ids"] = [timing_step_id]
    params["dcf_diag_dump_state_stats"] = 1 if scheme == "dcf" else 0
    params["dcf_diag_dump_pair_limit"] = 0
    params["dcf_diag_dump_topk"] = 1000
    params["dcf_diag_dump_term_grad_norms"] = 0
    params["dcf_diag_timing_steps_filename"] = "timing_steps_replay.jsonl"
    params["dcf_diag_save_snapshot_step_ids"] = []
    params["dcf_diag_replay_snapshot_dir"] = ""
    params["global_place_flag"] = 0
    params["legalize_flag"] = 0
    params["detailed_place_flag"] = 0
    params["random_center_init_flag"] = 0
    params["detailed_place_engine"] = ""
    params["result_dir"] = str(
        REPO_ROOT / "results" / "diagnostics_runtime_replay" / replay_tag / scheme
    )
    return params


def infer_output_dir(snapshot_dir: Path, scheme: str) -> Path:
    snapshot_metadata = load_json(snapshot_dir / "snapshot_metadata.json")
    timing_step_id = int(snapshot_metadata["timing_step_id"])
    source_scheme = snapshot_metadata["scheme_name"]
    case_name = snapshot_metadata["case_name"]
    return (
        REPO_ROOT
        / "results"
        / "diagnostics"
        / case_name
        / f"replay_from_{source_scheme}_step_{timing_step_id:03d}"
        / scheme
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--scheme", required=True, choices=["dcf", "pin2pin"])
    parser.add_argument("--output-dir")
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT))
    args = parser.parse_args()

    runtime_root = Path(args.runtime_root).resolve()
    snapshot_dir = Path(args.snapshot_dir).resolve()
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else infer_output_dir(snapshot_dir, args.scheme)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.root.name = "DREAMPlace"
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)-7s] %(name)s - %(message)s",
        stream=sys.stdout,
    )

    configure_imports(runtime_root)
    os.chdir(runtime_root)

    import Params
    import PlaceDB
    import Timer
    import BasicPlace
    import dcf_diagnostics
    import dreamplace.configure as configure

    snapshot_metadata = load_json(snapshot_dir / "snapshot_metadata.json")
    source_config = load_json(snapshot_dir / "config_used.json")
    replay_params_data = build_replay_params(
        source_config, snapshot_metadata, output_dir, args.scheme
    )

    params = Params.Params()
    params.fromJson(replay_params_data)
    os.environ["OMP_NUM_THREADS"] = str(params.num_threads)

    assert (not params.gpu) or configure.compile_configurations[
        "CUDA_FOUND"
    ] == "TRUE", "CANNOT enable GPU without CUDA compiled"

    placedb = PlaceDB.PlaceDB()
    placedb(params)

    timer = Timer.Timer()
    timer(params, placedb)
    timer.update_timing()

    placer = BasicPlace.BasicPlace(params, placedb, timer)
    diagnostics_mgr = dcf_diagnostics.DcfDiagnosticsManager(params, placedb)

    pos = torch.load(snapshot_dir / "pos.pt", map_location="cpu")
    if not isinstance(pos, torch.Tensor):
        raise TypeError("snapshot pos.pt must contain a tensor")
    expected_size = int(placedb.num_nodes * 2)
    if pos.numel() != expected_size:
        raise ValueError(
            f"snapshot position size {pos.numel()} does not match expected {expected_size}"
        )
    placer.pos[0].data.copy_(pos.to(placer.device, dtype=placer.pos[0].dtype))

    pos_cpu = placer.pos[0].data.detach().clone().cpu()
    position_fingerprint = diagnostics_mgr.position_fingerprint(pos_cpu)
    expected_fingerprint = snapshot_metadata.get("position_fingerprint")
    if expected_fingerprint and position_fingerprint != expected_fingerprint:
        raise ValueError(
            "snapshot position fingerprint mismatch: "
            f"expected {expected_fingerprint}, got {position_fingerprint}"
        )

    timing_op = placer.op_collections.timing_op
    timing_step_id = int(snapshot_metadata["timing_step_id"])
    gp_iter = int(snapshot_metadata.get("gp_iter", -1))
    npaths = max(1, int(placedb.num_nets * 0.03))

    replay_beg = time.time()
    timing_op(pos_cpu)
    timing_op.timer.update_timing()
    timing_diag = timing_op.update_net_weights(
        pos_cpu,
        max_net_weight=placedb.max_net_weight,
        n=npaths,
        diagnostics_step_id=timing_step_id,
        diagnostics_dump_step=(args.scheme == "dcf"),
    )
    if timing_diag is None:
        timing_diag = {}
    replay_runtime_sec = time.time() - replay_beg

    time_unit = timing_op.timer.time_unit()
    timing_summary = {
        "scheme_name": args.scheme,
        "timing_step_id": timing_step_id,
        "gp_iter": gp_iter,
        "npaths": npaths,
        "position_fingerprint": position_fingerprint,
        "TNS": float(timing_op.timer.report_tns_elw(split=1) / (time_unit * 1e17)),
        "WNS": float(timing_op.timer.report_wns(split=1) / (time_unit * 1e15)),
        "NVP": int(timing_op.timer.raw_timer.report_fep()),
        "timing_update_total_runtime_sec": replay_runtime_sec,
        "dcf_pass_runtime_sec": timing_diag.get("dcf_pass_runtime_sec"),
        "arcs_with_nonzero_mass": timing_diag.get("arcs_with_nonzero_mass"),
        "failing_endpoints_injected": timing_diag.get("failing_endpoints_injected"),
    }

    pair_summary = diagnostics_mgr.build_pair_summary(
        pos_cpu, placedb.pin2pin_net_weight
    )
    replay_metadata = {
        "source_snapshot_dir": str(snapshot_dir),
        "source_case_name": snapshot_metadata.get("case_name"),
        "source_scheme_name": snapshot_metadata.get("scheme_name"),
        "source_timing_step_id": timing_step_id,
        "source_gp_iter": gp_iter,
        "replay_scheme_name": args.scheme,
        "position_fingerprint": position_fingerprint,
        "snapshot_position_fingerprint": expected_fingerprint,
        "max_net_weight": placedb.max_net_weight,
        "npaths": npaths,
        "pair_summary": pair_summary,
        "timing_summary": timing_summary,
    }

    diagnostics_mgr.write_pair_rows(
        output_dir,
        pos_cpu,
        timing_step_id,
        gp_iter,
        placedb.pin2pin_net_weight,
        timing_diag,
    )
    diagnostics_mgr.write_state_stats(output_dir, timing_step_id, timing_diag)
    diagnostics_mgr.write_utility_summary(output_dir, timing_diag)
    diagnostics_mgr.write_position_fingerprint(output_dir, position_fingerprint)
    diagnostics_mgr.write_json(output_dir / "replay_metadata.json", replay_metadata)
    diagnostics_mgr.write_json(output_dir / "timing_summary.json", timing_summary)


if __name__ == "__main__":
    main()
