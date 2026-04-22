#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


BASELINES = {
    "superblue16": {
        "tns": "-22.604395",
        "wns": "-7.841117",
        "hpwl": "4.726394E+08",
        "runtime": "319.362",
    },
    "superblue3": {
        "tns": "-19.854089",
        "wns": "-11.724317",
        "hpwl": "4.628147E+08",
        "runtime": "554.147",
    },
    "superblue18": {
        "tns": "-15.976826",
        "wns": "-6.969738",
        "hpwl": "2.338593E+08",
        "runtime": "270.556",
    },
}

METHOD_ORDER = [
    ("efficient_tdp_readme", "Efficient-TDP", "-", "-"),
    ("dcf_v5_2_g025_l004_ref", "DCF v5.2 gated hybrid", "-", "0.20"),
    ("dcf_v6_local_rerank_w005", "DCF v6 local rerank", "0.05", "0.20"),
    ("dcf_v6_local_rerank_w010", "DCF v6 local rerank", "0.10", "0.20"),
    ("dcf_v6_local_rerank_w020", "DCF v6 local rerank", "0.20", "0.20"),
]

RERANK_METHODS = METHOD_ORDER[2:]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict[str, object]:
    with path.open() as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--tag", default="dcf_v6_local_rerank_stage1")
    parser.add_argument("--previous-tag", default="dcf_v5_2_g025_lambda_sweep")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result_root = root / "results" / args.tag
    previous_root = root / "results" / args.previous_tag
    debug_root = result_root / "hybrid_debug"
    artifacts_root = root / "docs" / "artifacts"

    metric_rows: list[dict[str, object]] = []
    for case_name, baseline in BASELINES.items():
        metric_rows.append(
            {
                "case": case_name,
                "method": "Efficient-TDP",
                "rerank_window_fraction": "-",
                "alpha": "-",
                "tns": baseline["tns"],
                "wns": baseline["wns"],
                "hpwl": baseline["hpwl"],
                "runtime": baseline["runtime"],
                "source": "README.research.md",
            }
        )
        previous_metrics = load_json(
            previous_root / "dcf_v5_2_g025_l004" / case_name / "metrics.json"
        )
        metric_rows.append(
            {
                "case": case_name,
                "method": "DCF v5.2 gated hybrid",
                "rerank_window_fraction": "-",
                "alpha": "0.20",
                "tns": previous_metrics["tns"],
                "wns": previous_metrics["wns"],
                "hpwl": previous_metrics["hpwl"],
                "runtime": previous_metrics["runtime"],
                "source": args.previous_tag,
            }
        )
        for method_key, method_name, window_fraction, alpha in RERANK_METHODS:
            metrics = load_json(result_root / method_key / case_name / "metrics.json")
            metric_rows.append(
                {
                    "case": case_name,
                    "method": method_name,
                    "rerank_window_fraction": window_fraction,
                    "alpha": alpha,
                    "tns": metrics["tns"],
                    "wns": metrics["wns"],
                    "hpwl": metrics["hpwl"],
                    "runtime": metrics["runtime"],
                    "source": args.tag,
                }
            )

    case_order = {case: idx for idx, case in enumerate(BASELINES)}
    method_order = {name: idx for idx, (_, name, _, _) in enumerate(METHOD_ORDER)}
    metric_rows.sort(
        key=lambda row: (
            case_order[row["case"]],
            method_order[row["method"]],
            row["rerank_window_fraction"],
        )
    )
    write_csv(
        artifacts_root / "dcf_v6_local_rerank_stage1_metrics.csv",
        metric_rows,
        [
            "case",
            "method",
            "rerank_window_fraction",
            "alpha",
            "tns",
            "wns",
            "hpwl",
            "runtime",
            "source",
        ],
    )

    engagement_rows: list[dict[str, object]] = []
    for case_name in BASELINES:
        for method_key, _, window_fraction, _ in RERANK_METHODS:
            summary = load_json(
                debug_root / case_name / method_key / "step_001" / "debug_summary.json"
            )
            engagement_rows.append(
                {
                    "case_name": case_name,
                    "rerank_window_fraction": window_fraction,
                    "first_timing_step_id": summary["timing_step_id"],
                    "base_pair_count": summary["raw_pin2pin"]["pair_count"],
                    "rerank_window_pair_count": summary[
                        "local_rerank_window_pair_count"
                    ],
                    "mapped_mhat_pair_count": summary["mapped_mhat"]["pair_count"],
                    "number_of_pairs_whose_local_order_changed": summary[
                        "local_rerank_pairs_order_changed"
                    ],
                    "exported_tensor_pair_count": summary["exported_tensor_view"][
                        "pair_count"
                    ],
                    "total_exported_weight_mass": summary["exported_tensor_view"][
                        "total_weight_mass"
                    ],
                }
            )
    engagement_rows.sort(
        key=lambda row: (case_order[row["case_name"]], float(row["rerank_window_fraction"]))
    )
    write_csv(
        artifacts_root / "dcf_v6_local_rerank_stage1_engagement_sanity.csv",
        engagement_rows,
        [
            "case_name",
            "rerank_window_fraction",
            "first_timing_step_id",
            "base_pair_count",
            "rerank_window_pair_count",
            "mapped_mhat_pair_count",
            "number_of_pairs_whose_local_order_changed",
            "exported_tensor_pair_count",
            "total_exported_weight_mass",
        ],
    )

    trajectory_rows: list[dict[str, object]] = []
    baseline_path = result_root / "diagnostics" / "superblue16" / "efficient_tdp_rerun" / "timing_steps.jsonl"
    if baseline_path.exists():
        with baseline_path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                trajectory_rows.append(
                    {
                        "timing_step_id": row["timing_step_id"],
                        "method": "Efficient-TDP",
                        "rerank_window_fraction": "-",
                        "tns": row["TNS"],
                        "wns": row["WNS"],
                        "exported_pair_count": row["exported_pair_count"],
                        "total_exported_weight_mass": row["total_exported_weight_mass"],
                    }
                )
    previous_path = previous_root / "diagnostics" / "superblue16" / "dcf_v5_2_g025_l004" / "timing_steps.jsonl"
    with previous_path.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            trajectory_rows.append(
                {
                    "timing_step_id": row["timing_step_id"],
                    "method": "DCF v5.2 gated hybrid",
                    "rerank_window_fraction": "-",
                    "tns": row["TNS"],
                    "wns": row["WNS"],
                    "exported_pair_count": row["exported_pair_count"],
                    "total_exported_weight_mass": row["total_exported_weight_mass"],
                }
            )
    for method_key, _, window_fraction, _ in RERANK_METHODS:
        path = result_root / "diagnostics" / "superblue16" / method_key / "timing_steps.jsonl"
        with path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                trajectory_rows.append(
                    {
                        "timing_step_id": row["timing_step_id"],
                        "method": "DCF v6 local rerank",
                        "rerank_window_fraction": window_fraction,
                        "tns": row["TNS"],
                        "wns": row["WNS"],
                        "exported_pair_count": row["exported_pair_count"],
                        "total_exported_weight_mass": row["total_exported_weight_mass"],
                    }
                )
    method_order_small = {"Efficient-TDP": 0, "DCF v5.2 gated hybrid": 1, "DCF v6 local rerank": 2}
    trajectory_rows.sort(
        key=lambda row: (
            method_order_small[row["method"]],
            row["rerank_window_fraction"],
            int(row["timing_step_id"]),
        )
    )
    write_csv(
        artifacts_root / "dcf_v6_local_rerank_superblue16_trajectory.csv",
        trajectory_rows,
        [
            "timing_step_id",
            "method",
            "rerank_window_fraction",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )


if __name__ == "__main__":
    main()
