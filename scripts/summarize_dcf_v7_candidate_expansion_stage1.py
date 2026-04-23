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
    ("dcf_v5_2_g025_l004_ref", "DCF v5.2 gated hybrid", "-"),
    ("dcf_v7_candidate_expansion_e001", "DCF v7 candidate expansion", "0.01"),
    ("dcf_v7_candidate_expansion_e002", "DCF v7 candidate expansion", "0.02"),
    ("dcf_v7_candidate_expansion_e005", "DCF v7 candidate expansion", "0.05"),
]

EXPANSION_METHODS = METHOD_ORDER[2:]


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
    parser.add_argument("--tag", default="dcf_v7_candidate_expansion_stage1")
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
                "expansion_size": "-",
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
                "expansion_size": "-",
                "tns": previous_metrics["tns"],
                "wns": previous_metrics["wns"],
                "hpwl": previous_metrics["hpwl"],
                "runtime": previous_metrics["runtime"],
                "source": args.previous_tag,
            }
        )
        for method_key, method_name, expansion_size in EXPANSION_METHODS:
            metrics = load_json(result_root / method_key / case_name / "metrics.json")
            metric_rows.append(
                {
                    "case": case_name,
                    "method": method_name,
                    "expansion_size": expansion_size,
                    "tns": metrics["tns"],
                    "wns": metrics["wns"],
                    "hpwl": metrics["hpwl"],
                    "runtime": metrics["runtime"],
                    "source": args.tag,
                }
            )

    case_order = {case: idx for idx, case in enumerate(BASELINES)}
    method_order = {name: idx for idx, (_, name, _) in enumerate(METHOD_ORDER)}
    metric_rows.sort(
        key=lambda row: (case_order[row["case"]], method_order[row["method"]], row["expansion_size"])
    )
    write_csv(
        artifacts_root / "dcf_v7_candidate_expansion_stage1_metrics.csv",
        metric_rows,
        [
            "case",
            "method",
            "expansion_size",
            "tns",
            "wns",
            "hpwl",
            "runtime",
            "source",
        ],
    )

    engagement_rows: list[dict[str, object]] = []
    for case_name in BASELINES:
        for method_key, _, expansion_size in EXPANSION_METHODS:
            summary = load_json(
                debug_root / case_name / method_key / "step_001" / "debug_summary.json"
            )
            engagement_rows.append(
                {
                    "case_name": case_name,
                    "expansion_size": expansion_size,
                    "first_timing_step_id": summary["timing_step_id"],
                    "base_pair_count": summary["raw_pin2pin"]["pair_count"],
                    "supplementary_pair_count": summary["candidate_expansion_pair_count"],
                    "supplementary_pair_fraction_actual": summary[
                        "candidate_expansion_pair_fraction_actual"
                    ],
                    "supplementary_pairs_with_nonzero_weight": summary[
                        "candidate_expansion_pairs_with_nonzero_weight"
                    ],
                    "final_exported_pair_count": summary["exported_tensor_view"]["pair_count"],
                    "base_total_weight_mass": summary[
                        "candidate_expansion_base_total_weight_mass"
                    ],
                    "supplementary_total_weight_mass": summary[
                        "candidate_expansion_supplementary_total_weight_mass"
                    ],
                    "final_exported_total_weight_mass": summary["exported_tensor_view"][
                        "total_weight_mass"
                    ],
                }
            )
    engagement_rows.sort(
        key=lambda row: (case_order[row["case_name"]], float(row["expansion_size"]))
    )
    write_csv(
        artifacts_root / "dcf_v7_candidate_expansion_stage1_engagement_sanity.csv",
        engagement_rows,
        [
            "case_name",
            "expansion_size",
            "first_timing_step_id",
            "base_pair_count",
            "supplementary_pair_count",
            "supplementary_pair_fraction_actual",
            "supplementary_pairs_with_nonzero_weight",
            "final_exported_pair_count",
            "base_total_weight_mass",
            "supplementary_total_weight_mass",
            "final_exported_total_weight_mass",
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
                        "expansion_size": "-",
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
                    "expansion_size": "-",
                    "tns": row["TNS"],
                    "wns": row["WNS"],
                    "exported_pair_count": row["exported_pair_count"],
                    "total_exported_weight_mass": row["total_exported_weight_mass"],
                }
            )
    for method_key, _, expansion_size in EXPANSION_METHODS:
        path = result_root / "diagnostics" / "superblue16" / method_key / "timing_steps.jsonl"
        with path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                trajectory_rows.append(
                    {
                        "timing_step_id": row["timing_step_id"],
                        "method": "DCF v7 candidate expansion",
                        "expansion_size": expansion_size,
                        "tns": row["TNS"],
                        "wns": row["WNS"],
                        "exported_pair_count": row["exported_pair_count"],
                        "total_exported_weight_mass": row["total_exported_weight_mass"],
                    }
                )
    method_order_small = {"Efficient-TDP": 0, "DCF v5.2 gated hybrid": 1, "DCF v7 candidate expansion": 2}
    trajectory_rows.sort(
        key=lambda row: (method_order_small[row["method"]], row["expansion_size"], int(row["timing_step_id"]))
    )
    write_csv(
        artifacts_root / "dcf_v7_candidate_expansion_superblue16_trajectory.csv",
        trajectory_rows,
        [
            "timing_step_id",
            "method",
            "expansion_size",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )


if __name__ == "__main__":
    main()
