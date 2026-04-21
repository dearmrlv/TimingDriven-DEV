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
    ("dcf_v5_1_gated_g025_l010", "DCF v5.1 gated hybrid", "0.10", "0.25"),
    ("dcf_v5_2_g025_l004", "DCF v5.2 gated hybrid", "0.04", "0.25"),
    ("dcf_v5_2_g025_l006", "DCF v5.2 gated hybrid", "0.06", "0.25"),
    ("dcf_v5_2_g025_l008", "DCF v5.2 gated hybrid", "0.08", "0.25"),
    ("dcf_v5_2_g025_l010", "DCF v5.2 gated hybrid", "0.10", "0.25"),
]

SWEEP_METHODS = METHOD_ORDER[1:]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--tag", default="dcf_v5_2_g025_lambda_sweep")
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
                "gate_fraction": "-",
                "tns": baseline["tns"],
                "wns": baseline["wns"],
                "hpwl": baseline["hpwl"],
                "runtime": baseline["runtime"],
                "source": "README.research.md",
            }
        )
        for method_key, method_name, lam, gate_fraction in SWEEP_METHODS:
            with (result_root / method_key / case_name / "metrics.json").open() as f:
                metrics = json.load(f)
            metric_rows.append(
                {
                    "case": case_name,
                    "method": method_name,
                    "method_key": method_key,
                    "lambda": lam,
                    "gate_fraction": gate_fraction,
                    "tns": metrics["tns"],
                    "wns": metrics["wns"],
                    "hpwl": metrics["hpwl"],
                    "runtime": metrics["runtime"],
                    "source": args.tag,
                }
            )

    case_order = {case: idx for idx, case in enumerate(BASELINES)}
    method_order = {key: idx for idx, (key, _, _, _) in enumerate(METHOD_ORDER)}
    metric_rows.sort(
        key=lambda row: (case_order[row["case"]], method_order[row["method_key"]])
    )
    write_csv(
        artifacts_root / "dcf_v5_2_g025_lambda_sweep_metrics.csv",
        metric_rows,
        [
            "case",
            "method",
            "method_key",
            "lambda",
            "gate_fraction",
            "tns",
            "wns",
            "hpwl",
            "runtime",
            "source",
        ],
    )

    engagement_rows: list[dict[str, object]] = []
    for case_name in BASELINES:
        for method_key, method_name, lam, gate_fraction in SWEEP_METHODS:
            summary_path = (
                debug_root / case_name / method_key / "step_001" / "debug_summary.json"
            )
            with summary_path.open() as f:
                summary = json.load(f)
            engagement_rows.append(
                {
                    "case_name": case_name,
                    "method": method_name,
                    "method_key": method_key,
                    "lambda": lam,
                    "gate_fraction": gate_fraction,
                    "first_timing_step_id": summary["timing_step_id"],
                    "base_pin2pin_pair_count": summary["raw_pin2pin"]["pair_count"],
                    "gated_pair_count": summary["hybrid_gate_pair_count"],
                    "gated_pair_fraction_actual": summary[
                        "hybrid_gate_pair_fraction_actual"
                    ],
                    "mapped_mhat_pair_count": summary["mapped_mhat"]["pair_count"],
                    "final_hybrid_pair_count": summary["final_hybrid_dict"][
                        "pair_count"
                    ],
                    "exported_tensor_pair_count": summary["exported_tensor_view"][
                        "pair_count"
                    ],
                    "final_hybrid_total_weight_mass": summary["final_hybrid_dict"][
                        "total_weight_mass"
                    ],
                    "exported_tensor_total_weight_mass": summary[
                        "exported_tensor_view"
                    ]["total_weight_mass"],
                }
            )
    engagement_rows.sort(
        key=lambda row: (case_order[row["case_name"]], float(row["lambda"]))
    )
    write_csv(
        artifacts_root / "dcf_v5_2_g025_lambda_sweep_engagement_sanity.csv",
        engagement_rows,
        [
            "case_name",
            "method",
            "method_key",
            "lambda",
            "gate_fraction",
            "first_timing_step_id",
            "base_pin2pin_pair_count",
            "gated_pair_count",
            "gated_pair_fraction_actual",
            "mapped_mhat_pair_count",
            "final_hybrid_pair_count",
            "exported_tensor_pair_count",
            "final_hybrid_total_weight_mass",
            "exported_tensor_total_weight_mass",
        ],
    )

    trajectory_rows: list[dict[str, object]] = []
    for method_key, method_name, lam, gate_fraction in SWEEP_METHODS:
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
                        "gate_fraction": gate_fraction,
                        "tns": row["TNS"],
                        "wns": row["WNS"],
                        "exported_pair_count": row["exported_pair_count"],
                        "total_exported_weight_mass": row[
                            "total_exported_weight_mass"
                        ],
                    }
                )
    trajectory_rows.sort(
        key=lambda row: (method_order[row["method_key"]], int(row["timing_step_id"]))
    )
    write_csv(
        artifacts_root / "dcf_v5_2_superblue16_trajectory.csv",
        trajectory_rows,
        [
            "timing_step_id",
            "method",
            "method_key",
            "lambda",
            "gate_fraction",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )


if __name__ == "__main__":
    main()
