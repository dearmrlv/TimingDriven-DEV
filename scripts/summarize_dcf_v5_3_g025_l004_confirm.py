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
    parser.add_argument("--previous-tag", default="dcf_v5_2_g025_lambda_sweep")
    parser.add_argument("--confirm-tag", default="dcf_v5_3_g025_l004_confirm")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    previous_root = root / "results" / args.previous_tag
    confirm_root = root / "results" / args.confirm_tag
    confirm_debug_root = confirm_root / "hybrid_debug"
    artifacts_root = root / "docs" / "artifacts"

    method_key_previous = "dcf_v5_2_g025_l004"
    method_key_confirm = "dcf_v5_3_g025_l004_confirm"

    metric_rows: list[dict[str, object]] = []
    for case_name, baseline in BASELINES.items():
        metric_rows.append(
            {
                "case": case_name,
                "method": "Efficient-TDP",
                "run_tag": "baseline",
                "gate_fraction": "-",
                "lambda": "-",
                "tns": baseline["tns"],
                "wns": baseline["wns"],
                "hpwl": baseline["hpwl"],
                "runtime": baseline["runtime"],
                "source": "README.research.md",
            }
        )

        previous_metrics = load_json(
            previous_root / method_key_previous / case_name / "metrics.json"
        )
        metric_rows.append(
            {
                "case": case_name,
                "method": previous_metrics["method"],
                "run_tag": "previous_best",
                "gate_fraction": "0.25",
                "lambda": "0.04",
                "tns": previous_metrics["tns"],
                "wns": previous_metrics["wns"],
                "hpwl": previous_metrics["hpwl"],
                "runtime": previous_metrics["runtime"],
                "source": args.previous_tag,
            }
        )

        confirm_metrics = load_json(
            confirm_root / method_key_confirm / case_name / "metrics.json"
        )
        metric_rows.append(
            {
                "case": case_name,
                "method": confirm_metrics["method"],
                "run_tag": "confirm_rerun",
                "gate_fraction": "0.25",
                "lambda": "0.04",
                "tns": confirm_metrics["tns"],
                "wns": confirm_metrics["wns"],
                "hpwl": confirm_metrics["hpwl"],
                "runtime": confirm_metrics["runtime"],
                "source": args.confirm_tag,
            }
        )

    case_order = {case: idx for idx, case in enumerate(BASELINES)}
    run_order = {"baseline": 0, "previous_best": 1, "confirm_rerun": 2}
    metric_rows.sort(key=lambda row: (case_order[row["case"]], run_order[row["run_tag"]]))
    write_csv(
        artifacts_root / "dcf_v5_3_g025_l004_confirm_metrics.csv",
        metric_rows,
        [
            "case",
            "method",
            "run_tag",
            "gate_fraction",
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
        summary = load_json(
            confirm_debug_root / case_name / method_key_confirm / "step_001" / "debug_summary.json"
        )
        engagement_rows.append(
            {
                "case_name": case_name,
                "first_timing_step_id": summary["timing_step_id"],
                "base_pin2pin_pair_count": summary["raw_pin2pin"]["pair_count"],
                "gated_pair_count": summary["hybrid_gate_pair_count"],
                "gated_pair_fraction_actual": summary["hybrid_gate_pair_fraction_actual"],
                "mapped_mhat_pair_count": summary["mapped_mhat"]["pair_count"],
                "final_hybrid_pair_count": summary["final_hybrid_dict"]["pair_count"],
                "exported_tensor_pair_count": summary["exported_tensor_view"]["pair_count"],
                "final_hybrid_total_weight_mass": summary["final_hybrid_dict"]["total_weight_mass"],
                "exported_tensor_total_weight_mass": summary["exported_tensor_view"]["total_weight_mass"],
            }
        )
    engagement_rows.sort(key=lambda row: case_order[row["case_name"]])
    write_csv(
        artifacts_root / "dcf_v5_3_g025_l004_confirm_engagement_sanity.csv",
        engagement_rows,
        [
            "case_name",
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
    for run_tag, base_dir, method_key in [
        ("previous_best", previous_root, method_key_previous),
        ("confirm_rerun", confirm_root, method_key_confirm),
    ]:
        path = base_dir / "diagnostics" / "superblue16" / method_key / "timing_steps.jsonl"
        with path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                trajectory_rows.append(
                    {
                        "timing_step_id": row["timing_step_id"],
                        "run_tag": run_tag,
                        "tns": row["TNS"],
                        "wns": row["WNS"],
                        "exported_pair_count": row["exported_pair_count"],
                        "total_exported_weight_mass": row["total_exported_weight_mass"],
                    }
                )
    run_order_small = {"previous_best": 0, "confirm_rerun": 1}
    trajectory_rows.sort(
        key=lambda row: (run_order_small[row["run_tag"]], int(row["timing_step_id"]))
    )
    write_csv(
        artifacts_root / "dcf_v5_3_superblue16_confirm_trajectory.csv",
        trajectory_rows,
        [
            "timing_step_id",
            "run_tag",
            "tns",
            "wns",
            "exported_pair_count",
            "total_exported_weight_mass",
        ],
    )


if __name__ == "__main__":
    main()
