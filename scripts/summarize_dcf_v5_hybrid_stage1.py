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
    ("efficient_tdp_readme", "Efficient-TDP", "-"),
    ("dcf_v3b", "DCF v3b", "-"),
    ("dcf_v4", "DCF v4", "-"),
    ("dcf_v5_hybrid_l010", "DCF v5 hybrid", "0.10"),
    ("dcf_v5_hybrid_l020", "DCF v5 hybrid", "0.20"),
    ("dcf_v5_hybrid_l030", "DCF v5 hybrid", "0.30"),
]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--tag", default="dcf_v5_hybrid_stage1")
    parser.add_argument("--debug-dir", default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result_root = root / "results" / args.tag
    debug_root = (
        Path(args.debug_dir).resolve()
        if args.debug_dir
        else result_root / "hybrid_debug"
    )
    artifacts_root = root / "docs" / "artifacts"

    metric_rows: list[dict[str, object]] = []
    for case_name, baseline in BASELINES.items():
        metric_rows.append(
            {
                "case": case_name,
                "method": "Efficient-TDP",
                "method_key": "efficient_tdp_readme",
                "lambda": "-",
                "tns": baseline["tns"],
                "wns": baseline["wns"],
                "hpwl": baseline["hpwl"],
                "runtime": baseline["runtime"],
                "source": "README.research.md",
            }
        )
        for method_key, method_name, lam in METHOD_ORDER[1:]:
            with (result_root / method_key / case_name / "metrics.json").open() as f:
                metrics = json.load(f)
            metric_rows.append(
                {
                    "case": case_name,
                    "method": method_name,
                    "method_key": method_key,
                    "lambda": lam,
                    "tns": metrics["tns"],
                    "wns": metrics["wns"],
                    "hpwl": metrics["hpwl"],
                    "runtime": metrics["runtime"],
                    "source": args.tag,
                }
            )

    case_order = {case: idx for idx, case in enumerate(BASELINES)}
    method_order = {key: idx for idx, (key, _, _) in enumerate(METHOD_ORDER)}
    metric_rows.sort(
        key=lambda row: (case_order[row["case"]], method_order[row["method_key"]])
    )
    write_csv(
        artifacts_root / "dcf_v5_hybrid_stage1_metrics.csv",
        metric_rows,
        [
            "case",
            "method",
            "method_key",
            "lambda",
            "tns",
            "wns",
            "hpwl",
            "runtime",
            "source",
        ],
    )

    engagement_rows: list[dict[str, object]] = []
    for case_name in BASELINES:
        for method_key, _, lam in METHOD_ORDER[3:]:
            summary_path = (
                debug_root / case_name / method_key / "step_001" / "debug_summary.json"
            )
            with summary_path.open() as f:
                summary = json.load(f)
            engagement_rows.append(
                {
                    "case_name": case_name,
                    "lambda": lam,
                    "first_timing_step_id": summary["timing_step_id"],
                    "base_pin2pin_pair_count": summary["raw_pin2pin"]["pair_count"],
                    "base_pin2pin_total_weight_mass": summary["raw_pin2pin"][
                        "total_weight_mass"
                    ],
                    "mapped_mhat_pair_count": summary["mapped_mhat"]["pair_count"],
                    "mapped_mhat_total_mass": summary["mapped_mhat"][
                        "total_weight_mass"
                    ],
                    "final_hybrid_pair_count": summary["final_hybrid_dict"][
                        "pair_count"
                    ],
                    "final_hybrid_total_weight_mass": summary["final_hybrid_dict"][
                        "total_weight_mass"
                    ],
                    "exported_tensor_pair_count": summary["exported_tensor_view"][
                        "pair_count"
                    ],
                    "exported_tensor_total_weight_mass": summary[
                        "exported_tensor_view"
                    ]["total_weight_mass"],
                    "top_pair_weight_before_export": summary["raw_pin2pin"][
                        "top_pair_weight"
                    ],
                    "top_pair_weight_after_export": summary["final_hybrid_dict"][
                        "top_pair_weight"
                    ],
                }
            )
    engagement_rows.sort(
        key=lambda row: (case_order[row["case_name"]], float(row["lambda"]))
    )
    write_csv(
        artifacts_root / "dcf_v5_hybrid_stage1_engagement_sanity.csv",
        engagement_rows,
        [
            "case_name",
            "lambda",
            "first_timing_step_id",
            "base_pin2pin_pair_count",
            "base_pin2pin_total_weight_mass",
            "mapped_mhat_pair_count",
            "mapped_mhat_total_mass",
            "final_hybrid_pair_count",
            "final_hybrid_total_weight_mass",
            "exported_tensor_pair_count",
            "exported_tensor_total_weight_mass",
            "top_pair_weight_before_export",
            "top_pair_weight_after_export",
        ],
    )

    trajectory_rows: list[dict[str, object]] = []
    for method_key, method_name, lam in METHOD_ORDER[1:]:
        path = (
            result_root
            / "diagnostics"
            / "superblue16"
            / method_key
            / "timing_steps.jsonl"
        )
        if not path.exists():
            continue
        with path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                trajectory_rows.append(
                    {
                        "timing_step_id": row["timing_step_id"],
                        "method": method_name,
                        "method_key": method_key,
                        "lambda": lam,
                        "tns": row["TNS"],
                        "wns": row["WNS"],
                        "exported_pair_count": row["exported_pair_count"],
                        "total_exported_weight_mass": row["total_exported_weight_mass"],
                    }
                )
    trajectory_rows.sort(
        key=lambda row: (method_order[row["method_key"]], int(row["timing_step_id"]))
    )
    write_csv(
        artifacts_root / "dcf_v5_hybrid_superblue16_trajectory.csv",
        trajectory_rows,
        [
            "timing_step_id",
            "method",
            "method_key",
            "lambda",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )


if __name__ == "__main__":
    main()
